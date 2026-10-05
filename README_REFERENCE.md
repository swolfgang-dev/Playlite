# Playlite

A native Linux game library with optional integrations.

## Install from GitHub

Playlite and plugin development repositories are private repositories under
`swolfgang-dev`. Authenticate once with `gh auth login`; your GitHub account must
have access to the repositories. Linux and Python 3.10 or later are required.

```sh
gh release download --repo swolfgang-dev/Playlite --pattern install.sh --dir /tmp/playlite-install
bash /tmp/playlite-install/install.sh
```

This installs the core application into a private environment at
`~/.local/share/playlite/runtime`, with desktop-menu and `~/.local/bin` launchers.
It includes the built-in Manual installation method and no plugin files.
An authenticated GitHub release download is used instead of public raw-file URLs.

Browse optional plugins through Settings → Plugins → Available. The [plugin catalogue](https://github.com/swolfgang-dev/Playlite/blob/main/catalogue.json) lives in this repository and points directly to plugin source repositories and their releases. The available list loads once in the background at startup and is cached for the session. Update list fetches it again when needed; opening settings or switching tabs does not make network requests. Only repositories accessible to this installation are listed. Repository builds offer Authenticate GitHub with browser sign-in and a one-time code, or a personal access token with read access to the plugin repositories; credentials are stored with owner-only permissions in that installation’s data directory, independently of your normal GitHub CLI login. Release builds always browse and download anonymously, so private plugins remain hidden.

You can also use Settings → Plugins → Installed → Install / update
from GitHub, or use `playlite-plugins install OWNER/REPOSITORY`. Each plugin is
fetched from its own checksummed release, and must be followed by a restart.

| Plugin | Distribution repository |
| --- | --- |
| Steam Metadata | [playlite-plugin-steam-metadata](https://github.com/swolfgang-dev/playlite-plugin-steam-metadata) |
| IGDB | [playlite-plugin-igdb](https://github.com/swolfgang-dev/playlite-plugin-igdb) |
| Lutris Integration | [playlite-plugin-lutris](https://github.com/swolfgang-dev/playlite-plugin-lutris) |
| Game Archiver | [playlite-plugin-game-archiver](https://github.com/swolfgang-dev/playlite-plugin-game-archiver) |
| SteamAutoCrack | [playlite-plugin-steamautocrack](https://github.com/swolfgang-dev/playlite-plugin-steamautocrack) |
| Icon Studio | [playlite-plugin-icon-studio](https://github.com/swolfgang-dev/playlite-plugin-icon-studio) |

Plugin implementations and integration tests belong to those repositories. Core
release builds check that no optional plugin implementation enters the wheel.
Push a `v*` tag to publish a new GitHub release; plugin repositories have their own
release workflows. Existing library data and plugin settings are preserved.

## Initial scope

- Import a copy of the existing Playnite library, metadata, and artwork.
- Browse, search, sort, and filter games.
- Show a header image with Play and Edit buttons, a cover beside a rounded description and details panel, links, and an installation folder section.
- Add standalone games through the existing Standalone Game Manager integration.
- Allow editing installation folders and Wine prefix locations.
- Launch games through Lutris and track playtime.
- Look up metadata and artwork.

## Technical direction

Python with PyQt6/Qt for the native interface, using the Qt binding already installed on this system. Reuse the Standalone Game Manager's registration logic where appropriate.

Default standalone installation root: `~/Games/`.

Default game prefix root: `~/.local/share/playlite/prefixes/`.

Develop alongside Playnite, importing copies rather than modifying its library. Existing Playnite plugins will require individual integrations or replacements.

## Status

The native library view includes a searchable game list, artwork header, Play/Edit buttons, cover beside a rounded metadata panel, links, and an installation folder section. Play opens the existing Lutris entry. Edit opens a full metadata editor and saves into Playlite's own snapshot; it does not move game files or update Lutris.

## Run

On this machine, PyQt6 is available to `/usr/bin/python3`:

```bash
cd /path/to/playlite
/usr/bin/python3 -m playlite
```

On another system, install this project in a Python virtual environment with `pip install -e .` and run `playlite`.

The initial 21-game snapshot comes from the existing Standalone Game Manager export, with copies of available artwork from Playnite. It is stored at `~/.local/share/playlite/library.json` and is not a live synchronization with Playnite. Artwork whose exported filename no longer exists is selected from that game's artwork folder by image shape.

To import another JSON export:

```bash
/usr/bin/python3 tools/import_snapshot.py /path/to/export.json /path/to/Playnite/library/files
```

Importing replaces Playlite's snapshot. Pass `--destination /path/to/folder` to create a separate snapshot, then launch with `--data /path/to/folder`.

The initial export omitted Features. Those assignments were recovered from copies of Playnite's `games.db` and `features.db` using `tools/feature_export`, and merged into Playlite's snapshot. Future imports can preserve them with `--features ~/.local/state/playlite/features.json`. The export helper requires .NET 8 and a build property `PlayniteDirectory` pointing to the directory containing Playnite's `LiteDB.dll`; its arguments are the copied database directory and output JSON path.

The metadata editor includes general fields, scores, dates, play statistics, installed/favorite/hidden flags, developers, publishers, platforms, genres, features, tags, categories, series, age ratings, regions, description, notes, links, artwork, installation folder, prefix, and Lutris game ID. Artwork selections are copied into Playlite. Saves are atomic and retain the previous library as `library.json.bak`. Cancel discards changes. Prefix and folder fields are descriptive and do not reconfigure Lutris. New fields absent from the initial export start blank.

Search, selection, links, folder opening, metadata editing, metadata downloads, Lutris launching, running detection, and automatic playtime tracking are wired up. Direct Playnite database import and Lutris prefix configuration remain future work.

## Library views

**Settings → Appearance** controls background blur, side-panel transparency,
and game-panel transparency. Slider help appears beneath each bar. The Colours
list provides 21 saved pickers for shared colour roles, including menus, text, borders,
selection highlights, painted controls, and placeholder artwork. Colours shared
by several elements use one picker. Save applies changes; Cancel discards edits.
**Reset colours to defaults** restores the selected theme’s palette when saved.
Theme plugins can provide palettes using stable role names; individual colours
can be customised after choosing a theme.

The toolbar switches between a game list and a wrapping cover grid; both retain the selected game's details on the right. Sort by name, release date, developer, publisher, date added, last played, playtime, or user score in ascending or descending order. Missing sort values appear last. An optional sorting name overrides the displayed name for alphabetical sorting.

**Filters** opens controls for genre, platform, feature, developer, publisher, source, completion status, installation state, favorites, and hidden games. Filters combine with title search. Hidden games are excluded unless **Show hidden games** is checked. **Clear filters** resets filters and search. The selected view, sorting, filters, and game are saved in Playlite's `ui.ini`.

Run editor tests with `/usr/bin/python3 -m unittest discover -s tests -v`.

## Download metadata

Steam artwork is integrated into the Steam metadata plugin. **Download metadata…**
includes checkboxes for Icon, Cover, Header, and Background alongside text fields;
Steam recommends artwork for each selected type and skips unavailable candidates.
On the editor's **Images** tab, **Download images…** opens a manual picker with
four tabs, each with its own provider selector and game search. Search text is
shared between tabs using the same provider; searching loads the current image
type. A single game result is selected automatically; multiple results open a picker.
Choose images, then **Apply** and **Save**. No Steam API key is required.

Open **Edit → Download metadata…**. The downloader follows Playnite's organization: open Download metadata on the Metadata tab or Download images on the Images tab, then select fields and their source, then match the game, then compare conflicting current and downloaded values. The initial provider is Steam, with no API key required. You can download only missing fields and save field selections as defaults. Name downloading is opt-in by default. Search by title or enter a Steam app ID/store URL; existing Steam links are used as the initial lookup. Select the match and press **Select** (or double-click it). Missing values fill automatically; equal values are ignored. For conflicts, choose Current or Downloaded for scalar fields and select individual current/downloaded entries for list fields. Selected images are downloaded before comparison and displayed as thumbnails; identical files are ignored. **Apply** fills the editor; **Save** commits the changes. Canceling the editor discards them.

Available Steam fields include name, short description, developers, publishers, genres, features, supported platforms, release date, and a Metacritic score when supplied. Link comparisons select existing links by default; deselect any you do not want to retain. Missing provider fields do not clear existing metadata. The separate image downloader selects cover and header artwork by default and downloads them into temporary storage, copied into Playlite on Save. Network requests run in background tasks with timeouts and visible error messages. An unavailable image does not block other downloaded fields. The public Steam store endpoints and optional artwork assets can change or be unavailable.

Behavior was checked against `GameEditViewModelMetadata.cs` and `MetadataComparisonViewModel.cs` in the Playnite reference. This reproduces the single-game comparison workflow; SteamGridDB, multiple providers with fallback priority, and bulk library downloads are not implemented yet.

## Reference source

A separate clone of upstream [Playnite](https://github.com/JosefNemec/Playnite) is available at `../playnite-reference` for studying library models, metadata, launching, and import behavior. Keep reference code separate from Playlite and check upstream licensing when reusing code.


Use **Add Game…** in the toolbar, then choose Manual, or an installed integration’s add/import method from the Integration dropdown on Installation. Switching methods preserves installation fields and each method’s controls. Review metadata and images on their respective tabs; Installation contains executable, folder, and Wine prefix fields. Folder selection describes existing files and does not move them.

**Lutris Integration** supplies both Lutris add methods, launching, and background running detection. Add to Lutris creates or reuses a Lutris Wine entry; Import from Lutris selects an existing entry. Lutris must have been opened once to create its database. Existing games can configure named play actions and their integrations on Edit → Installation. Each action has a card containing its integration, game ID, executable, Wine prefix, arguments, and optional folder override. Move-up, move-down, and Remove controls manage the launch order. The installation folder remains shared for size calculation and archiving; existing integration launch settings migrate into actions when saved. Play launches a single action directly or opens a chooser for multiple actions. Detection follows Lutris game sessions, including games started outside Playlite, and updates Play to Launching or Running. Confirmed sessions record play time, last played, and play count, with periodic saves while Playlite is running.

SteamAutoCrack is a native Linux plugin. Open **Settings → Plugins → Installation → SteamAutoCrack** to configure the emulator username, optional Steam Web API key, processing timeout, emulator libraries, and native unpacker. **Install / update native tools…** downloads Goldberg libraries and builds the original Steamless x86/x64 variants with a private Linux .NET SDK; native 7-Zip (`7z` or `7zz`) is required for setup. Processing uses Python and Linux .NET, without the Windows CLI or a Wine prefix. Source references and licensing details are in [the plugin documentation](https://github.com/swolfgang-dev/playlite-plugin-steamautocrack/blob/main/NATIVE_TOOLS.md).

Set a Steam metadata ID, then use **SteamAutoCrack: Run…** from a game's context menu or Play dropdown. Running games are blocked. Steam game-info generation requires a Web API key; it can be disabled while retaining emulator configuration and application. Automatic processing after adding is optional, with a separate saved default for each add method. Processing stages changes, verifies original backups, and rolls back on cancellation or failure. **Restore originals…** restores backed-up files while preserving unrelated settings and saves. Native job state lives under `~/.local/state/playlite/steamautocrack`, and tools under `~/.local/share/playlite/steamautocrack/tools`.

Metadata and artwork now have separate download actions on their respective editor tabs. Each action has independent saved field selections and applies only that kind of data. SteamDB is not a downloader provider: it has no public API and disallows automated scraping; Steam and IGDB are available as metadata and artwork sources.


IGDB is available in the downloader’s **Source** selector. Open **Playlite Settings → Metadata** and enter the Client ID and Client Secret from your Twitch developer application ([IGDB setup](https://api-docs.igdb.com/#account-creation)). Credentials are saved in `~/.config/playlite/igdb.json` with owner-only read/write permissions; OAuth tokens stay in memory and refresh on expiry. Alternatively set `PLAYLITE_IGDB_CLIENT_ID` and `PLAYLITE_IGDB_CLIENT_SECRET`. IGDB searches accept a title, numeric IGDB game ID, or IGDB game URL. Source choices are remembered separately for metadata and images. A download uses one provider; changing a field source switches the whole download to that source.

IGDB supplies description and storyline, developers, publishers, genres, platforms, game modes as Features, keywords as Tags, themes as Categories, collections/franchises as Series, release date, critic/community scores, and website links when available. Its cover and artwork/screenshot downloads remain confined to the Images workflow. Missing fields preserve existing values. IGDB authentication, normalization, matching, and download isolation were tested with mocked API responses; a live authenticated request requires user credentials.

The Metadata editor uses two columns of compact label-and-input rows, with General, Links, and Advanced sections on one scrollable page. List fields can be edited inline as CSV, in a one-value-per-line popup, or with the add-value button. Link rows support editing, reordering, and removal. Images and Installation remain separate tabs.

Playlite runs as a single instance per Linux user. Launching it again restores the running window. Closing the main window hides it and open dialogs to the system tray, preserving unsaved edits and allowing background work to continue. Use the tray icon or its Show Playlite action to restore them; Quit Playlite exits, cancelling and waiting for any active SteamAutoCrack job. On desktops without a system tray, closing exits instead. Dialogs leave the main close button available, including file selectors and metadata windows.

The application icon replacing the pink P matches the desktop/tray icon and opens Settings. General contains the close-to-tray preference; Metadata contains source defaults and IGDB credentials. The default window is 1540×1060, and window geometry is remembered across full quits.

Download metadata and Download images appear in the fixed bottom-left editor footer only on their respective tabs. Nested dialogs remain enabled so metadata search, selection, and application work while keeping the main close button available.

The enlarged logo has a transparent background and opens the application menu on click or right-click. Add Game and Settings are available there.

Images use preview cards for Icon, Cover, Header, and Background, including dimensions and file/URL/remove/browser-search controls. Header and Background are independent fields. Legacy BackgroundImage artwork is interpreted as Header until the game is saved in the new format, preserving existing hero artwork. A newly assigned Background appears dimmed behind the library details; Header remains the hero image. The image downloader offers cover, header, and background selections independently.

Settings → Plugins → Installed lists enabled and disabled plugins with their version, type, status, ID, description, and location. Use Ctrl/Shift to select multiple rows: Delete selected removes installed plugin files while preserving library entries; Install selected in Available installs all selected plugins and reports individual results. Restart Playlite to load or unload plugins. Settings tabs omit plugins without configuration or contributed controls.

**Game Archiver** is enabled under Settings → Plugins → General. Choose
an existing game library root and add one or more archive folders using the
folder pickers. Right-click a game (or open its Play dropdown) to choose Archive
or Restore. Archiving moves a verified copy into the selected archive while
preserving its relative path; restoring returns it to the original location.
Launching an archived game offers to restore it first. Running games are blocked,
Lutris registrations and Wine prefixes are preserved, and cancellation keeps the
source until the verified destination and library record have been committed.
The current plugin moves folders without compression and rejects symlinks and
special files.

Select multiple games with Ctrl-click or Shift-click in list or grid view. Right-click the selection for batch deletion and supported plugin actions. Deleting entries keeps installation folders, archives, and Wine prefixes. Archived games show an archive icon and location in the installation panel. Edit → Installation → Archive information records an existing archive without moving files.
