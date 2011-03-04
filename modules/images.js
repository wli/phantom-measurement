phantom.modules = phantom.modules || {};
phantom.modules.images = {
  run: function() {
    var imgs = document.getElementsByTagName('img');
    return _.map(imgs, function(node) { return node.src; });
  }
};
