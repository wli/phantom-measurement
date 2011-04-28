phantom.modules = phantom.modules || {};
phantom.modules.links = {
  run: function() {
    var links = [];
    _.each(document.getElementsByTagName('a'), function(elem) {
      if (elem && elem.href && elem.href.search(/^http/) !== -1)
        links.push([elem.href, (elem.offsetWidth * elem.offsetHeight) || 0]);
    });
    
    /* Compute area taken by each link */
    var totalArea = _.reduce(links, function(total, link) { return total + link[1]; }, 0);
    var result = {};
    if (totalArea == 0) {
      var numLinks = links.length;
      _.each(links, function(link) {
        result[link[0]] = 1. / numLinks;
      });
    } else {
      _.each(links, function(link) {
        if (result[link[0]]) result[link[0]] += link[1] / totalArea;
        else result[link[0]] = link[1] / totalArea;
      });
    }
    return result;
  }
};
