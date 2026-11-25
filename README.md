# Atelier

A local-first desktop studio for level layouts, character relationships and world history. The Windows client uses Python 3.11+ with Tk and SQLite. The collaboration service can run separately on a shared host.

Projects use stable record IDs. A 2D layout stores planar coordinates and a 3D blockout uses a right-handed, Y-up coordinate system. Images are keyed by SHA-256. Portable project archives contain a versioned project.json and an assets directory.

