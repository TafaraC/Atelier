# Atelier

Atelier is a Windows desktop studio for planning levels, character relationships and world history. A project can hold both 2D layouts and 3D blockouts. All three workspaces share the same character, faction, event and lore records.

## Run or install

Use Python 3.11 or later with Tk support. No pip packages are required.

- Double-click **Launch Atelier.cmd**, or run `python -m atelier` from this repository.
- For a per-user installation with a Start menu shortcut, run `.\install.ps1` in PowerShell. Installing the application requires an existing Python installation. Re-running the installer updates the installed code.
- Local projects and images are stored in `%USERPROFILE%\.atelier\studio.sqlite`. Set `ATELIER_HOME` before launch to select a different data directory. Use a separate data directory for each running client.

## Plan a game

1. Open **Project → New project**, name the notebook, then choose **New level**. Choose **2D** for a planar layout or **3D** for a Y-up blockout. Design type is fixed at creation.
2. Choose a drawing tool above the canvas. Drag to size a room, region, ramp or other primitive. Choose **Marker** or **Text** to add a label. With **Route**, click each waypoint and choose **Finish route**. A route's properties accept relative waypoint coordinates, including elevation in 3D.
3. Choose **Select** and click an object to inspect it. Drag to move it on the drawing plane. Edit its properties for exact position, size, rotation, notes, mechanics, loot, narrative relevance and prerequisites. In 2D the first rotation value is the planar angle in degrees. **Edit → Duplicate placement** copies geometry. **Edit → Frame selection** centres it.
4. Use the wheel to zoom and the middle button to pan. Right-drag to orbit a 3D level. Switch to Top, Front or Side for axis-aligned placement. Add a drawing layer from **Create**, select it in the toolbar and edit its properties to hide or lock it. Use layers for floors and overlays.
5. Create characters and factions, then create a graph. **Place profile** adds a movable reference. **Relationship** connects two profiles. Reuse a profile in another graph and its name updates across both. **Follow reference** opens its canonical record.
6. Create events, eras and lore from **Create**. On a timeline, **Add track** and **Place event / era** assign a numeric interval for plotting. Store approximate dates, disputed accounts and revelations in the event's properties. Change the timeline origin and spacing in its inspector. The same event can appear on multiple tracks.
7. **Link record** connects the selection to a character, faction, event, era, level or lore entry. The explorer search includes descriptions and notes. **Ctrl+Z** and **Ctrl+Y** undo and redo local edits during the current project session.

Project edits save automatically. **Project → Export archive** writes a portable ZIP-format `.atelier` file containing versioned JSON and original image bytes. Import creates an independent copy with remapped IDs. JSON-only export is available for inspecting structured data. Image placement supports PNG and GIF.

## Share across devices

The repository includes a self-hosted service backed by a separate SQLite database. Both desktop clients must be able to reach the same service. Nothing is provisioned or published automatically.

For a single-machine trial, run the following in another terminal:

```powershell
python -m atelier.server --database atelier-cloud.sqlite
```

For a remote host, either forward HTTPS through a reverse proxy to the loopback service, or give the service a certificate and key trusted by the clients:

```powershell
python -m atelier.server --bind 0.0.0.0 --port 8462 --cert fullchain.pem --key privkey.pem --database atelier-cloud.sqlite
```

Back up the service database. Apply deployment-level request limits before exposing the service publicly. Each complete project archive is limited to 64 MiB uncompressed.

1. In **Collaboration**, enter the service URL, register a named account, save the private recovery code and sign in. Password reset uses that code.
2. The owner chooses **Publish project**, then **Invite**. Give the invitation code to the intended account holder. Codes expire after seven days.
3. On the second device, sign in, **Accept invitation**, then **Download**. The downloaded project remains available offline.
4. **Sync** after editing or enable the minute timer while the collaboration panel is open and signed in. The service transfers complete archives and checks the shared revision before writing. Independent record edits merge automatically. Concurrent edits or edit/delete conflicts on one record require a choice. Inconsistent cross-record merges stop with an error and retain the local project. Archive the local version before resolving extensive conflicts.
5. Viewers can download. Editors can upload edits. Administrators can also invite and revoke editors and viewers. Revocation blocks future access to the hosted copy. Existing offline copies remain on the device.

## Verification and implementation scope

Run `python -m unittest discover -s tests -v`. Desktop tests create temporary SQLite databases and open Tk windows. Collaboration tests exercise the HTTP handler with two independent clients. Set `ATELIER_TEST_NETWORK=1` to run the collaboration test over a loopback socket.

This implementation covers the three planning workflows, portable archives and asynchronous collaboration. The design specification also describes features beyond this release, including advanced canvas tools and multi-selection, typed bidirectional reference browsing, additional image and document formats, richer relationship filtering, section clipping, an installer with a bundled runtime, and entity-level network transfers. The renderer is a conceptual drafting tool. Overlapping or intersecting 3D faces can show drawing-order artifacts.
