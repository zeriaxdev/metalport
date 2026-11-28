"""Behaviour of tools/dissonance_stub.c (pass-through AudioPluginDissonance). Needs clang; skipped elsewhere."""
import ctypes, math, os, shutil, subprocess, tempfile, unittest

SRC = os.path.join(os.path.dirname(__file__), '..', 'tools', 'dissonance_stub.c')
F = ctypes.c_float


@unittest.skipUnless(shutil.which('clang'), 'clang not available')
class DissonanceStub(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.log = os.environ['MP_DISSONANCE_LOG'] = os.path.join(cls.tmp.name, 'stub.log')
        out = os.path.join(cls.tmp.name, 'libdissonance_stub.dylib')
        subprocess.run(['clang', '-dynamiclib', '-Wno-everything', SRC, '-o', out], check=True)
        lib = cls.lib = ctypes.CDLL(out)
        lib.Dissonance_CreatePreprocessor.restype = ctypes.c_void_p
        lib.Dissonance_CreatePreprocessor.argtypes = [ctypes.c_int] * 7
        lib.Dissonance_DestroyPreprocessor.argtypes = [ctypes.c_void_p]
        lib.Dissonance_GetVadSpeechState.argtypes = [ctypes.c_void_p]
        lib.Dissonance_PreprocessCaptureFrame.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int]

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def frame(self, amp):
        return (F * 480)(*[amp * math.sin(i / 7) for i in range(480)])

    def test_speech_state_follows_loudness_with_hangover(self):
        lib = self.lib; h = lib.Dissonance_CreatePreprocessor(1, 1, 0, 0, 0, 0, 0)
        loud, quiet = self.frame(0.2), self.frame(0.0)
        self.assertEqual(lib.Dissonance_PreprocessCaptureFrame(h, 48000, loud, loud, 0), 0)
        self.assertEqual(lib.Dissonance_GetVadSpeechState(h), 1)
        for _ in range(25): lib.Dissonance_PreprocessCaptureFrame(h, 48000, quiet, quiet, 0)
        self.assertEqual(lib.Dissonance_GetVadSpeechState(h), 1)       # still inside the 250 ms hang-over
        for _ in range(2): lib.Dissonance_PreprocessCaptureFrame(h, 48000, quiet, quiet, 0)
        self.assertEqual(lib.Dissonance_GetVadSpeechState(h), 0)
        lib.Dissonance_DestroyPreprocessor(h)
        text = open(self.log).read()
        self.assertIn('speech start', text); self.assertIn('speech stop', text)    # the diagnostic log records both edges

    def test_detection_works_while_the_game_reports_output_muted(self):
        # The game mutes the output until it starts transmitting; detection must still fire or voice activation never starts.
        lib = self.lib; h = lib.Dissonance_CreatePreprocessor(1, 1, 0, 0, 0, 0, 0)
        lib.Dissonance_SetAgcIsOutputMutedState.argtypes = [ctypes.c_void_p, ctypes.c_int]
        lib.Dissonance_SetAgcIsOutputMutedState(h, 1)
        loud = self.frame(0.2)
        lib.Dissonance_PreprocessCaptureFrame(h, 48000, loud, loud, 0)
        self.assertEqual(lib.Dissonance_GetVadSpeechState(h), 1)
        lib.Dissonance_DestroyPreprocessor(h)

    def test_audio_passes_through_and_errors_are_reported(self):
        lib = self.lib; h = lib.Dissonance_CreatePreprocessor(1, 1, 0, 0, 0, 0, 0)
        src, dst = self.frame(0.3), (F * 480)()
        self.assertEqual(lib.Dissonance_PreprocessCaptureFrame(h, 48000, src, dst, 0), 0)
        self.assertEqual(list(dst), list(src))
        self.assertEqual(lib.Dissonance_PreprocessCaptureFrame(h, 44100, src, dst, 0), -7)   # BadSampleRate
        self.assertEqual(lib.Dissonance_PreprocessCaptureFrame(None, 48000, src, dst, 0), -5)  # NullPointer
        lib.Dissonance_DestroyPreprocessor(h)


if __name__ == '__main__':
    unittest.main()
