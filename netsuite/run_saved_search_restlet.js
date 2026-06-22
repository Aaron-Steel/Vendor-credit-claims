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

  function cellValue(result, col) {
    // getValue reproduces the saved-search/Excel output the importer expects (prices as
    // raw numbers, status as its value). Coerce to a JSON-safe primitive and never throw.
    var v;
    try { v = result.getValue(col); } catch (e) { return ''; }
    if (v === null || v === undefined) return '';
    if (typeof v === 'object') return String(v);   // e.g. a Date -> string
    return v;
  }

  function runSavedSearch(searchId) {
    var s = search.load({ id: searchId });
    var columns = s.columns;
    var rows = [];
    var paged = s.runPaged({ pageSize: 1000 });
    paged.pageRanges.forEach(function (range) {
      var page = paged.fetch({ index: range.index });
      page.data.forEach(function (result) {
        var obj = {};
        for (var i = 0; i < columns.length; i++) {
          var col = columns[i];
          var key = col.label || col.name;
          obj[key] = cellValue(result, col);
        }
        rows.push(obj);
      });
    });
    return rows;
  }

  function handle(context) {
    try {
      var searchId = context.searchId || (context.body && context.body.searchId);
      if (!searchId) {
        return { error: 'searchId is required' };
      }
      return runSavedSearch(searchId);
    } catch (e) {
      // surface the real cause (e.g. permission/search errors) instead of a generic
      // UNEXPECTED_ERROR, so the caller can see what went wrong.
      return { error: (e && e.name) || 'error',
               message: (e && e.message) || String(e),
               detail: (e && e.stack) ? String(e.stack).split('\n')[0] : undefined };
    }
  }

  return { get: handle, post: handle };
});
