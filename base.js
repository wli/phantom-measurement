(function() {
  phantom.userAgent = 'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/534.24 (KHTML, like Gecko) Chrome/11.0.696.50 Safari/534.24';
  if (phantom.state.length === 0) {
    // Setup
    if (phantom.args.length !== 2) {
      console.log('No URL and output path specified! Read the source code.');
      phantom.exit();
    } else if (!phantom.modules) {
      console.log('Nothing to run.');
      phantom.exit();
    } else {
      phantom.state = 'run';
      phantom.open(phantom.args[0]);
    }
  } else {
    if (phantom.loadStatus === 'success') {
      var results = {"url": window.location.href, "original_url": phantom.args[0]};
      for (var name in phantom.modules) {
        try {
          results[name] = phantom.modules[name].run();
        } catch(e) {
          results[name] = '!!! EXCEPTION !!! ' + e.toString();
        }
      }
    } else {
      var results = {"failed_to_load": true};
    }

    phantom.setOutputPath(phantom.args[1]);
    phantom.write(JSON.stringify(results));
    phantom.exit();
  }
})();
