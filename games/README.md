# Game data

One JSON file per game: Steam ids, depot/manifest (= exactly which game version a port was verified on), engine facts, plugin handling, status,
known issues and lessons. Update a file whenever a port is (re)built or a game updates.

* `supported_versions` is the contract: compare the installed depot manifest (`app_info_print <appid>` in the Steam console) with it.
* Personal data never goes here (no Steam ids, friend names, local paths with the username, emails).
* Library triage (which games to try next) is personal, so it lives in `library-candidates.local.md` (git-ignored).
