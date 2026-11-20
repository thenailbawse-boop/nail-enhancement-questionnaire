// Creator Reset — relays planning requests from the popup to the iPhone app's
// extension (SafariWebExtensionHandler.swift), where the on-device Apple model runs.
// Safari ignores the application id on iOS; the containing app's extension answers.
browser.runtime.onMessage.addListener((message) => {
  if (message && message.type === "native") {
    return browser.runtime.sendNativeMessage("application.id", message.payload);
  }
  return undefined;
});
