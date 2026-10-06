# Downloads

The Downloads button stays at the bottom of the library sidebar in list, grid,
and compact modes. It opens a tray that slides up over the game view, showing
active downloads, waiting games, progress, and completed or failed jobs. Closing
the tray or switching games does not stop downloading.

Steam Depot Downloader uses **Add to queue** when opened from the Playlite menu.
Choose a game, platform, optional DLC, and an empty destination. Its prepared
manifest selection is retained by the queue, so the selection window can close
or prepare another game while downloading continues. Games download sequentially;
base-game and DLC depots remain grouped as one game job. Downloads require the
isolated VPN and saved Steam authentication. A queued job reconnects with saved
VPN credentials if needed before starting a worker.

Remove a waiting game or cancel the active download from the tray. Failed and
cancelled jobs retain incomplete files in staging; only validated completed output
is promoted to the destination. Completed jobs offer **Open folder** and **Add to
Playlite**. **Clear finished** removes queue history, not downloaded files.

The queue is held in memory for the application session. Closing Playlite cancels
active and waiting jobs; restart recovery is not implemented. Plugins can enqueue
jobs through `window.download_queue.enqueue(name, destination, factory)`, where the
factory receives the queue and entry and returns a controller exposing `start()`
and `cancel()`. Controllers report progress with `update` and completion with
`finish`. An optional `dispose()` releases completed controllers when history is
cleared.
