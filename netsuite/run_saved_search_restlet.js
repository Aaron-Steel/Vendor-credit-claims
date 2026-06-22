/**
 * Run a saved search by ID and return all its rows as JSON.
 *
 * Deployed as a RESTlet so n8n (with token-based auth) can pull the master price
 * level searches headlessly. Each row is keyed by the search column's label,
 * matching exactly what the saved search shows (and what the app's importer expects).
 *
 * Call (GET):  <restlet-url>&searchId=customsearch1084
 * Returns:     [ { "Code": "...", "Base (RRP Inc)": "169.99", "JB HIFI": "...", ... }, ... ]
 *
 * @NApiVersion 2.1
 * @NScriptType Restlet
 */
define(['N/search'], function (search) {

  function runSavedSearch(searchId) {
    var s = search.load({ id: searchId });
    var columns = s.columns;
    var rows = [];
    var paged = s.runPaged({ pageSize: 1000 });
    paged.pageRanges.forEach(function (range) {
      var page = paged.fetch({ index: range.index });
      page.data.forEach(function (result) {
        var obj = {};
        columns.forEach(function (col) {
          var key = col.label || col.name;
          // getValue reproduces the saved-search/Excel output the importer expects
          // (prices as raw numbers, status as its value). If a list field ever comes
          // back as an internal id, switch that column to result.getText(col).
          obj[key] = result.getValue(col);
        });
        rows.push(obj);
      });
    });
    return rows;
  }

  function handle(context) {
    var searchId = context.searchId || (context.body && context.body.searchId);
    if (!searchId) {
      return { error: 'searchId is required' };
    }
    return runSavedSearch(searchId);
  }

  return { get: handle, post: handle };
});
