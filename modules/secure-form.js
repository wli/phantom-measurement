phantom.modules = phantom.modules || {};
phantom.modules.secureForm = {
  run: function() {
    var passwordFields = phantom.util.forAllChildFrames(function(doc) {
      var result = [];
      _.each(doc.getElementsByTagName('input'), function(inputElem) {
        if (inputElem && inputElem.type && inputElem.type == 'password')
          result.push(inputElem);
      });
      return result;
    });

    if (passwordFields.length > 0) {
      var actions = {'formless': 0, 'unknownAction': 0, 'javascript': 0, 'http': 0, 'https': 0};
      _.each(passwordFields, function(pwElem) {
        if (!pwElem.form) {
          actions.formless += 1; 
          return;
        }

        if (!pwElem.form.action) {
          actions.unknownAction += 1;
          return;
        }
        
        if (pwElem.form.action.search(/^https/) !== -1)
          actions.https += 1;
        else if (pwElem.form.action.search(/^http/) !== -1)
          actions.http += 1;
        else if (pwElem.form.action.search(/^javascript/) !== -1)
          actions.javascript += 1;
        else
          actions.unknownAction += 1;
      });

      return actions;
    }
  }
};
