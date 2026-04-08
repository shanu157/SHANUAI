const { autoUpdater } = require('electron-updater');
autoUpdater.checkForUpdatesAndNotify();
autoUpdater.on('update-downloaded', () => {
  autoUpdater.quitAndInstall();
});

const { autoUpdater } = require('electron-updater');

app.on('ready', () => {
  autoUpdater.checkForUpdatesAndNotify();
});

autoUpdater.on('update-downloaded', () => {
  autoUpdater.quitAndInstall();
});
