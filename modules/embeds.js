phantom.modules = phantom.modules || {};
phantom.modules.embeds = {
  run: function() {
    var embeds = phantom.util.forAllChildFrames(function(doc) {
      var result = [];
      _.each(doc.getElementsByTagName('embed'), function(elem) {
        if (elem && elem.src)
          result.push(elem.src);
      });
      return result;
    });

    var applets = phantom.util.forAllChildFrames(function(doc) {
      var result = [];
      _.each(doc.getElementsByTagName('applet'), function(elem) {
        if (elem && elem.src)
          result.push(elem.src);
      });
      return result;
    });

    var objects = phantom.util.forAllChildFrames(function(doc) {
      var result = [];
      _.each(doc.getElementsByTagName('object'), function(elem) {
        if (elem && elem.data)
          result.push(elem.data);
      });
      return result;
    });

    return _.uniq(Array.prototype.concat(embeds, applets, objects));
  }
};
