(function() {
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
    var results = {"url": window.location.href, "original_url": phantom.args[0]};
    for (var name in phantom.modules) {
      results[name] = phantom.modules[name].run();
    }

    phantom.setOutputPath(phantom.args[1]);
    phantom.write(JSON.stringify(results));
    phantom.exit();
  }
})();
