if (phantom.state.length === 0) {
  // Setup
  if (phantom.args.length !== 1) {
    console.log('No URL specified! Read the source code.');
    phantom.exit();
  } else if (!phantom.modules) {
    console.log('Nothing to run.');
    phantom.exit();
  } else {
    phantom.state = 'run';
    phantom.open(phantom.args[0]);
} else {
  results = {};
  for (var name in phantom.modules) {
    results[name] = phantom.modules[name].run());
  }
  console.log(results);
  phantom.exit();
}
