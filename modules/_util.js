phantom.util = phantom.util || {};
phantom.util.forEachFrame = function(doc, fn) {
  var allFrames = [];
  var iframes = doc.getElementsByTagName('iframe');
  var frames = doc.getElementsByTagName('frame');

  for (var i = 0, end = iframes.length; i < end; ++i)
    allFrames.push(iframes[i]);

  for (var i = 0, end = frames.length; i < end; ++i)
    allFrames.push(frames[i]);

  _.each(allFrames, fn);
}

phantom.util.forAllChildFrames = function(fn) {
  var result = [];
  var queue = [document];

  while (queue.length > 0) {
    var doc = queue.shift();
    Array.prototype.push.apply(result, fn(doc));

    console.log(result);

    phantom.util.forEachFrame(doc, function(elem) {
      if (elem.contentWindow && elem.contentWindow.document) 
        queue.push(elem.contentWindow.document);
    });
  }

  return result;
};
