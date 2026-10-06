# Metadata plugins

All plugins are optional and distributed from their own repositories. Plugins live in
`~/.local/share/playlite/plugins/<plugin-folder>/` (or under `$XDG_DATA_HOME`).
They load when a downloader opens. Each folder contains `manifest.json` and
`plugin.py`. Plugins run Python code with the app's access to your machine.
Search and fetch run on worker threads; they must not manipulate Qt widgets.
Use finite network timeouts. This API does not run plugins in isolated processes.

Example manifest:

```json
{
  "id": "MySource",
  "name": "My Source",
  "version": "1.0.0",
  "api_version": 1,
  "fields": ["Name", "SortingName", "Description", "Links", "CoverImage"]
}
```

Keep `id` stable: game associations and review defaults use it as their key.
It must be unique and cannot be `Current`. The optional provider IDs remain `Steam`
and `IGDB`, preserving existing saved IDs and defaults. Supported field names
are listed in the plugin manifests. Unsupported fields are disabled in the UI.

Example `plugin.py`:

```python
from playlite.providers import MetadataProvider

class Provider(MetadataProvider):
    def search(self, query):
        # Search your service using the query (name, saved ID, or URL).
        return [{"id": "123", "name": "Example Game"}]

    def fetch(self, game_id, fields):
        # fields is the set requested by the user.
        return {
            "id": game_id,
            "name": "Example Game",
            "fields": {"Name": "Example Game", "Links": []},
            "images": {"CoverImage": "https://example.com/cover.jpg"},
        }
```

`fields` contains metadata values, while `images` contains download URLs keyed
by artwork field. The downloader downloads artwork and presents results for
review before applying changes. List fields use arrays; links use
`{"Name": "Official Website", "Url": "https://example.com"}` objects.
Release dates use `{"ReleaseDate": "YYYY-MM-DD"}`. Developers, Publishers,
and Series are treated as single fields in the editor and picker.

Optional methods:

- `linked_query(game)` returns a saved-link URL or ID, or `None`.
- `is_exact_query(query, result_id=None)` identifies direct ID/URL lookups;
  when a result ID is supplied, verify it matches if possible. Only a single
  exact result is selected automatically.
- `query_hint` supplies search placeholder text.
- `create_settings(parent)` returns a Qt widget for the plugin's page in Settings
  → Plugins, or `None` if there are no settings. `save_settings(widget)` validates
  and saves it when the user clicks Save; raise `ValueError` for invalid input.
  These two hooks run on the UI thread.

Plugins can own their credential configuration. IGDB keeps its existing Twitch
credentials and application settings screen; Steam requires no credentials.
Do not embed secrets in manifests. Discovery errors are logged and that plugin
is skipped; other providers remain available.

See the `playlite-plugin-steam-metadata` and `playlite-plugin-igdb` repositories for working adapters.

## Game providers and generic plugins

Set `"type": "game"` or `"type": "generic"` in the manifest and export a
`Plugin` class instead of `Provider`. These types do not declare metadata fields
and do not appear in the metadata source tables. All types appear in Settings →
Plugins and share the settings hooks above.

Game plugins inherit `GameProvider`. Implement `owns(game)`, `association_id(game)`,
`import_games()`, and `launch(game)`. Imported entries use Playlite's game schema
and UUIDs, plus `GameProvider` and `ProviderGameId` for their association. The
Lutris adapter preserves the existing `LutrisId` field for compatibility. Import
actions appear in the application menu; existing associations are not duplicated.

Generic plugins inherit `GenericPlugin`. Available hooks are:

- `game_actions(window, game)`: return `(title, callback)` pairs for the shared
  Play-button and list/grid context menu.
- `before_launch(window, game)`: return `False` to cancel launching. Archiver uses
  this to offer restoration before launching an archived game.
- `augment_add_editor(editor)`: add plugin controls to the add-game dialog.
- `prepare_add(editor, game, registration)`: validate preparation before
  registration. SteamAutoCrack builds its request here.
- `after_game_added(window, game, editor)`: run follow-up work after the game is
  saved, such as the SteamAutoCrack progress dialog.

Game actions and lifecycle hooks run on the UI thread. Plugins must move lengthy
operations to a worker; plugin tools already do so. Lutris launching uses native
Lutris. SteamAutoCrack uses a native Python pipeline and locally built Linux
Steamless unpackers; see [the native plugin documentation](native-steamautocrack.md).

Playlite Archiver preserves relative paths below its configured source root and
supports multiple archive folders. Transfers copy into a temporary folder,
verify SHA-256 contents and source stability, commit the destination and library
record, then remove the source. Lutris entries and Wine prefixes stay unchanged.
It rejects collisions, nested paths, symlinks and special files, and supports
cancellation before commit. One transfer runs at a time. Keep games stopped
during transfers. After a crash or failed cleanup, retain any `.partial-*` or
`.moving-*` folders until both locations have been checked. The native port
currently operates on one game at a time and does not migrate old Playnite
archive records.

### Installation methods

A manifest with `"type": "installation"` exports `Plugin(InstallationPlugin)`.
`create_editor(editor, game)` returns the method's QWidget, and
`collect(widget, game)` validates controls and returns the proposed game record.
These methods must not create prefixes, register external games, or modify game
files. Manual is a built-in installation method, not a discovered plugin, selected in the Add
Game editor. It stores `InstallationMethod`, `InstallDirectory`, `Executable`,
and `LaunchArguments`; blank installation details are supported.

### Command line

Run `playlite-cli` after installation, or `python3 -m playlite.cli` from the
repository. Installation plugins expose `cli_name`, `configure_cli(parser)`,
`cli_game(args, plugins)`, and optionally `cli_commit(args, game, plugins)`.
Validation must happen in `cli_game`; only `cli_commit` may change external state.

Examples:

```sh
python3 -m playlite.cli manual --exe /games/Example/game.exe
python3 -m playlite.cli import-lutris --lutris-id 42
python3 -m playlite.cli add-lutris --exe /games/Example/game.exe --prefix /prefixes/example --runner GE-Proton --create-prefix
```

Each command accepts `--dry-run`. Use `--data /path/to/library` before the command
to select another library. Close the GUI before CLI writes; the CLI shares its
instance lock to avoid concurrent edits. SteamAutoCrack is not triggered by these
commands. Successful output is the saved entry as JSON.

### Image providers

The Steam metadata plugin also supplies selectable artwork, available through
**Edit → Images → Download images…**. Search by title, app ID, or store
URL; the saved Steam metadata ID or link supplies the initial query. Select a
game in the Icon, Cover, Header, or Background tab. Each tab has its own provider
selector and search controls; search text is shared only between tabs using the
same provider. Searches download candidates for the current type. A single game
result is selected automatically; multiple results open a selection window.
Tabs sharing the same provider and search reuse one downloaded image catalogue.
Opening a tab resets its filters to the saved defaults for that image type. Artwork, shape, and resolution use dropdowns of checkboxes with multiple selections
and an All checkbox. Resolution ranges use the longest image edge. Selections
within a group combine; images must match each group. Filter changes require no network requests,
and any visible image can be assigned to any type. Each tab retains its selection. Double-click an image to select
it; a thick blue border marks the chosen image. Repeat for other image types, then **Apply** and save the
editor. Cancel discards the selections. Existing manual controls remain available.

Switching tabs automatically searches when the query is a provider ID or exact
game URL. Results already loaded for the same provider and query are retained.

Settings → Plugins → Metadata → General settings includes separate default
providers and artwork, shape, and resolution checkbox filters for Icon, Cover,
Header, and Background. Defaults apply when opening tabs and using Reset filters. Each selector lists providers
offering artwork, which can be used for any image type. Saved defaults initialize the corresponding image-picker
tabs; unavailable providers fall back to an available source.

Steam combines the third-party [SteamCMD API](https://github.com/steamcmd/api)
app-info catalogue with Steam's store API. Searches include advertised localized
and high-resolution library artwork, client/community icons, logos, store
capsules, backgrounds, screenshots, and trailer posters. CDN aliases are
deduplicated, and complete catalogues are cached for five minutes across tabs.
Each source can operate when the other is unavailable. The community page is an
icon fallback. No API key is required. ICO, TGA, and Linux ZIP icons are converted
to PNG; multi-image icons use their largest image. Missing assets are skipped.
This covers currently advertised assets, rather than historical or removed
SteamDB images. Requests run in worker threads with finite timeouts.

The metadata field table also offers all four image types as checkboxes in each
provider column. Selected types use that plugin's candidates in preference order,
trying the next candidate when an optional asset is unavailable. Results appear
alongside the other metadata for review before applying to the editor.

Metadata plugins can declare `image_types` (a set of artwork field names) and
implement `images(game_id, image_type)` to return candidates with `url`, `label`,
and optional `thumbnail`, ordered from most to least appropriate. The image picker uses the same plugin ID, search,
and saved metadata associations. An optional `query(game)` supplies the initial
search; the default uses the saved metadata ID, linked query, then game name.

### Settings contributions

Any plugin can implement `create_settings_contribution(target, parent)` and
return a widget to place inside another installed plugin's settings section.
Return `None` for targets that do not apply. Playlite calls
`save_settings_contribution(target, widget)` on the contributing plugin when
settings are saved. The contributor owns persistence; construction must not
write settings. No contribution appears if either plugin is absent.

SteamAutoCrack contributes an independent run-after-add default to each
installation method. Its legacy shared default is used until a method-specific
value is saved. Opening an add method initializes the editor toggle to that
method's default. Username and timeout stay in SteamAutoCrack's own section.


Steam and IGDB metadata are enabled. Configure IGDB's Twitch application
Client ID and Client Secret in Plugins → Metadata → IGDB. IGDB supplies covers,
artworks, and screenshots through the shared image downloader; each game catalogue
is cached across tabs. Images use the documented 1080p retina variant to retain
aspect ratio. Metadata requests use the current website type fields.
Disabled plugins are omitted from discovery and settings; their saved metadata
IDs and credentials are retained.

Steam metadata offers separate `Description` (short summary) and
`FullDescription` (`about_the_game` HTML) fields. Embedded images are excluded.
The game view shows the full description in a separate card, truncated and
collapsed by default. Clicking the description animates its expansion and centers
it in the game page where possible. A centered Hide button collapses it.
The description has no inner border and uses edge fades with internal scrolling.
The Hide button appears only while expanded.

Image Studio is an optional general plugin (`ImageStudio`) and is disabled by default.
When enabled, its `augment_editor` hook adds the crop/frame tool to the Images
page in both Edit and Add game windows. The tool and its dialog live entirely
inside `playlite/plugins/icon_studio`.

### Theme plugins

A theme uses the same plugin folders and manifest format, with `"type": "theme"`.
Its `plugin.py` exports a `Plugin` subclass of `playlite.providers.ThemePlugin`:

```python
from playlite.providers import ThemePlugin

class Plugin(ThemePlugin):
    def palette(self):
        return {"window": "#101112", "accent": "#2196f3", "text": "#e9e9e9"}
```

Appearance lists enabled theme plugins in the Theme selector. Palette keys are
stable role names from `playlite.theme.ROLES`: `window`, `sidebar`, `panel`,
`popup`, `control`, `hover`, `disabled_surface`, `selection`, `accent`, `border`,
`divider`, `scrollbar`, `text`, `secondary_text`, `disabled_text`, `placeholder`,
`brand`, `error`, `play_surface`, `play_text`, and `shadow`. Missing or invalid
colours fall back to Playlite defaults. User colour overrides take precedence;
selecting another theme or resetting colours fills the pickers with its base
palette, and Save applies the result. Cancel leaves saved settings unchanged.
Panel transparency remains independent of the theme palette.

Existing hexadecimal colour settings migrate to these roles on Save. When
several former colours share a role, a customised canonical colour takes
precedence, followed by the first customised alias. Styles, painted widgets,
and UI SVGs resolve through the same palette.

## Launcher integrations

A manifest with `"type": "integration"` exports `Plugin(IntegrationPlugin)`.
Integrations own launching, importing and running-game detection. Lutris is one
integration, with both **Add to Lutris** and **Import from Lutris** entry points.
Its plugin ID is `LutrisIntegration`; game associations use the `LutrisId` field.

Implement the `GameProvider` hooks above, plus:

- `installation_methods()`: return `InstallationPlugin` objects with stable
  `id`, `name`, `type="installation"` and `version` attributes. These supply
  Installation dropdown choices and CLI commands within a single integration.
- `detect_running(games)`: return the IDs of confirmed running Playlite entries.
  This executes in a worker and must not access Qt widgets. Raise on detector
  failure; a failed scan must not falsely mark every game stopped.

The Installation tab of an existing game assigns integrations to its play
actions. Legacy entries use `GameProvider`; an explicit `null` means no
integration and overrides legacy association inference. Add dialogs select their installation method through the Integration dropdown
on the Installation page. Choosing an integration does not alter external
launcher configuration.

Playlite polls integrations once a second and publishes `Launching`, `Running`,
`Stopped`, and `Launch failed` status. Launch confirmation times out after 60
seconds; a two-second absence grace period accommodates process hand-offs.
Lutris groups same-user processes by `LUTRIS_GAME_UUID`, matches game paths and
Wine prefixes, ignores zombies and ambiguous matches, and can detect games
launched directly in Lutris. Confirmed sessions increment `PlayCount`, update
`LastActivity` with a timezone-aware timestamp, and accumulate `Playtime` in
whole seconds using a monotonic clock. History is saved on confirmation, every
30 seconds, on confirmed stop, and when Playlite exits. The stop grace period
is excluded from elapsed time; brief process hand-offs retain the same session.
Tracking requires Playlite to remain running (including in the system tray).

### Play actions

Existing entries expose individual play-action cards on Installation, with
identity and integration fields on the left and launch settings on the right.
Each card has move-up, move-down, and remove controls. Each named action owns its
integration, game ID, executable, Wine prefix, launch arguments, and optional
installation folder override. The shared installation folder remains on the entry. The
integration is attached to the action; `PlayActions` is the entry's ordered list
of launch choices. An empty list disables launching. Entries without this field
retain their previous integration as one implicit action. Add methods are selected through the Installation page dropdown.

`GameProvider.launch_action(game, action)` delegates to the integration's launch
implementation using a copy of the entry. `action_id_field` identifies the
integration's ID field (default `ProviderGameId`, `LutrisId` for Lutris), and
`validate_action(action)` checks optional IDs. Plugins can override these hooks
for additional launch behavior. Missing integrations are retained in the editor
and report an error when selected for launch.

One action launches directly. Multiple actions open a named-action picker;
cancelling launches nothing. Before-launch hooks run after selection. Lutris
running detection resolves all configured action IDs and records history once
for the Playlite entry, including when an alternate action is launched externally.

Integrations can implement `create_action_editor(action, parent)` to supply their
own launch controls. Return a QWidget with `collect()` returning action fields;
the default `LaunchSettings` supplies executable/prefix path pickers, arguments,
and an installation-folder override. Unknown action properties survive edits.
Legacy entry-level launch settings are copied into actions when the editor opens
and removed from integration-linked entries when saved. Empty arguments and
prefixes explicitly clear those settings; an empty folder override uses the shared
installation folder. Metadata, artwork, archiving, and aggregate play history
remain properties of the game entry.


## Plugin names and folders

Plugin IDs use the displayed name without spaces. Repository folders and installed
plugin folders use the same `playlite-plugin-` name.

| Name | ID | Repository / folder |
| --- | --- | --- |
| Game Archiver | `GameArchiver` | `playlite-plugin-game-archiver` |
| IGDB | `IGDB` | `playlite-plugin-igdb` |
| Image Studio | `ImageStudio` | `playlite-plugin-image-studio` |
| Lutris Integration | `LutrisIntegration` | `playlite-plugin-lutris-integration` |
| Steam Depot Downloader | `SteamDepotDownloader` | `playlite-plugin-steam-depot-downloader` |
| Steam Integration | `SteamIntegration` | `playlite-plugin-steam-integration` |
| Steam Metadata | `SteamMetadata` | `playlite-plugin-steam-metadata` |
| SteamAutoCrack | `SteamAutoCrack` | `playlite-plugin-steamautocrack` |
| SteamGridDB | `SteamGridDB` | `playlite-plugin-steamgriddb` |

Plugin settings stores retain their existing namespaces for configured folders
and credentials. Updates match installed plugins by their current IDs and
preserve the enabled state.

Plugins may declare `image_defaults` in their manifest, keyed by image type.
Each entry uses `artwork`, `shape`, and `resolution` lists with values from
`playlite.image_filters.OPTIONS`. The declaring plugin becomes that image type's
initial provider. Installation seeds preferences only when they are unset;
updates and additional installations preserve explicit user choices. Installed
plugin declarations also supply defaults for profiles without saved preferences.
