// Adds flat-API accessors that this Steam API library predates, by asking steamclient directly.
extern void* SteamInternal_FindOrCreateUserInterface(int user, const char* version);
extern int SteamAPI_GetHSteamUser(void);
extern int SteamGameServer_GetHSteamUser(void);
void* SteamAPI_SteamUGC_v020(void)            { return SteamInternal_FindOrCreateUserInterface(SteamAPI_GetHSteamUser(), "STEAMUGC_INTERFACE_VERSION020"); }
void* SteamAPI_SteamUserStats_v013(void)      { return SteamInternal_FindOrCreateUserInterface(SteamAPI_GetHSteamUser(), "STEAMUSERSTATS_INTERFACE_VERSION013"); }
void* SteamAPI_SteamVideo_v007(void)          { return SteamInternal_FindOrCreateUserInterface(SteamAPI_GetHSteamUser(), "STEAMVIDEO_INTERFACE_V007"); }
void* SteamAPI_SteamTimeline_v004(void)       { return SteamInternal_FindOrCreateUserInterface(SteamAPI_GetHSteamUser(), "STEAMTIMELINE_INTERFACE_V004"); }
void* SteamAPI_SteamGameServerUGC_v020(void)  { return SteamInternal_FindOrCreateUserInterface(SteamGameServer_GetHSteamUser(), "STEAMUGC_INTERFACE_VERSION020"); }
