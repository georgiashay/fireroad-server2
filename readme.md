# FireRoad Server

FireRoad is an iOS/Android (and hopefully soon, web) application providing MIT students with accessible information about courses, subjects, and schedules. The FireRoad Server is a Django server that currently provides simple catalog auto-updating services but is intended to expand into course suggestion features later on.

The `master` branch of this repo is intended to be checked out and run by the production server. All changes not ready for `master` should be kept in the `develop` branch.

## Cloning and Setup

Follow these instructions to set up and run your own instance of the FireRoad server. *This repo is currently designed to work with Python 2.7 and Django 1.7.10.*

Once you have checked out the repo, you will need to generate a secret key, for example:

```
$ cd fireroad-server
$ openssl rand -base64 80 > fireroad/secret.txt
```

You will need a SQL server - we use SQLite for local testing and MySQL for production. (If using MySQL, follow instructions in the MySQL note below *before* running the migration commands. If using SQLite, a database file will be automatically created.) Using an environment with the appropriate Python/Django versions, run the following commands to build the database:

```
python manage.py makemigrations common catalog sync recommend requirements
python manage.py migrate
```

**MySQL note:** To set up a MySQL database, you will need to create a file called `dbcreds.py` within the (inner) `fireroad` directory that defines the following variables: `dbname`, `username`, `password`, and `host`. These are used to initialize the MySQL database in `settings.py`. To work with the login-based APIs, you will need a file at `recommend/oidc.txt` that contains two lines: one with the client ID and one with the client secret for the OAuth authorization server.

### Merging Notes

**Read this before you merge into master.** The develop and master branches contain different versions of `fireroad/settings.py`, which are critical for the different server behaviors in local development and production. To merge into master, try using the following to merge without modifying the settings file:

```
git merge --no-ff --no-commit <merge-branch>
git reset HEAD fireroad/settings.py
git checkout -- fireroad/settings.py
```

If you made any changes you want to keep in the settings file for production, you would need to redo those changes before committing the merge.

## Login Procedures

**Please remember to use the dev server (fireroad-dev.mit.edu) for all local testing, and _only_ use the production server (fireroad.mit.edu) for your production application.** The workflow for logging into the FireRoad server as a web application is as follows:

1. Your site sends the user to `<FIREROAD>/login`, with an optional query parameter `sem` indicating the user's current semester, and required query parameter `redirect` indicating the redirect URL after login. For production, this redirect URL needs to be registered with FireRoad before use.
2. The FireRoad server handles login through MIT OpenID Connect, creates a FireRoad account if necessary, then sends the user back to your redirect URL, passing a query parameter `code`.
3. The code is a string that can be used exactly once within 5 minutes of login to retrieve an access token. The application server does this by sending a request to `<FIREROAD>/fetch_token`, passing the query parameter `code` received in step 2.
4. The FireRoad server validates the temporary code and sends the application server back a JSON web token (JWT) that can be used to authorize use of the API.
5. The application server uses the JWT by including the `Authorization` header set to `"Bearer <base-64 encoded token string>"` in any request to the FireRoad server.
6. Since the JWT may expire, the application server should check its validity by requesting the `/verify/` endpoint with the `Authorization` header. If the token is expired or invalid, this endpoint will return 403, indicating that the user should log in again.

## API Endpoints

*(Up-to-date as of 1/26/2019)* All endpoints in `recommend`, `prefs`, and `sync` require login. See "Login Procedures" above for information on how to use the authentication system.

### Authentication

* `/signup/`: Displays a user-facing page that specifies the conditions of allowing recommendations.

* `/login/`: Redirects to the OAuth page (URL specified in `common/oauth_client.py`) to log the user in. See "Login Procedures" for how to log in as a web client. **Note:** Web clients *must* include a `redirect` query parameter. Requests without a `redirect` parameter will be treated as coming from a native (mobile) app, and will transfer the token to the client in a way that is **not secure** outside of a native app.

* `/fetch_token/`: Takes a query parameter `code` and, if it is valid and unexpired, returns the associated access token. See "Login Procedures" above for more details.

* `/verify/` *(GET)*: Checks that the user is logged in, and if so, auto-increments the user's current semester and returns the new semester.

* `/user_info/` *(GET)*: (Requires authentication) Returns a JSON object containing information about the current user, including the following keys:

  * `academic_id`: the user's institution email address
  * `current_semester`: the user's current semester (numbered 0),
  * `name`: the user's full name
  * `username` the user's username on the FireRoad server (not human-readable)

### Course Updater

* `/courseupdater/semesters/` *(GET)*: Returns a JSON list specifying the order of the semesters available on the server, as well as their current version numbers.

* `/courseupdater/check/` *(GET)*: Given a semester and local version number, returns a new version number and the delta of catalog files that should be updated. Takes as query parameters:

  * `sem`, a comma-separated specification of the semester (e.g. "fall,2018")
  * `v`, the local version number of the catalog

### Course Catalog

* `/courses/lookup/<subject ID>` *(GET)*: Returns a JSON description of the course with the given subject ID, or a 404 error if the course is not present.

* `/courses/dept/<dept code>` *(GET)*: Returns a JSON list containing all subjects in the given department (the subject ID prefix, such as "6", "WGS"), in numerically sorted order. If the department does not exist, returns an empty list. Takes Boolean query parameter `full`, indicating whether to return the full set of information for each subject or an abbreviated version.

* `/courses/all` *(GET)*: Returns a JSON list of all courses in the current version of the catalog, in numerically sorted order. Takes Boolean query parameter `full`, indicating whether to return the full set of information for each subject or an abbreviated version.

* `/courses/search/<search term>` *(GET)*: Returns a JSON list of courses for the given search term. Currently only the subject ID and subject title are searched. Takes Boolean query parameter `full`, indicating whether to return the full set of information for each subject or an abbreviated version. Also takes query parameters to filter the results:

  * `type`: The match type to use with the search term. Possible values: "contains" (default), "matches", "starts", "ends"
  * `gir`: Filter by GIR requirement. Possible values: "off" (default), "any", "lab", "rest"
  * `hass`: Filter by HASS requirement. Possible values: "off" (default), "any", "a", "s", "h"
  * `ci`: Filter by communication requirement. Possible values: "off" (default), "cih", "cihw", "not-ci"
  * `offered`: Filter by semester offered. Possible values: "off" (default), "fall", "spring", "IAP", "summer"
  * `level`: Filter by course level. Possible values: "off" (default), "undergrad", "grad"

### Recommender

* `/recommend/rate/` *(POST)*: The body of the request should be a JSON list of dictionaries, each containing `s` (subject ID) and `v` (rating value). Updates the ratings for each item.

* `/recommend/get/` *(GET)*: Takes an optional parameter `t` indicating the type of recommendation to return. Returns a dictionary of recommendation types mapped to JSON strings indicating the recommended subjects and their rating values.

### User Preferences

* `/prefs/notes/` *(GET)*, `/prefs/set_notes/` *(POST)*: These endpoints handle read-write of notes, which the user can enter for any subject in the catalog. The format of the returned notes is a dictionary with the `success` key, and if that is true, a `notes` key containing a dictionary keyed by subject IDs.

* `/prefs/favorites/` *(GET)*, `/prefs/set_favorites/` *(POST)*: These endpoints handle read-write of favorite subjects. The format of the returned data is a dictionary with the `success` key, and if that is true, a `favorites` key containing a list of subject IDs.

* `/prefs/progress_overrides/` *(GET)*, `/prefs/set_progress_overrides/` *(POST)*: **Deprecated: use the `progressOverrides` key in the road file to store progress overrides.** These endpoints handle read-write of manual progress overrides, which the user can set for requirements lists to indicate progress toward completion. The format of the returned data is a dictionary with the `success` key, and if that is true, a `progress_overrides` key containing a dictionary keyed by requirements list key-paths (see the `RequirementsListStatement` implementation in the mobile app for more information).

* `/prefs/custom_courses/` *(GET)*, `/prefs/set_custom_course/` *(POST)*, and `/prefs/remove_custom_course/` *(POST)*: Endpoints to manage custom courses created by the user. The input and output JSON formats are as follows:

  * `custom_courses`: no input, output is `{"success": <bool>, "custom_courses": <list of custom courses in standard JSON course format>}`.
  * `set_custom_course`: input is a JSON dictionary containing the full description of a course to add or update (`subject_id` is required). By default, the course is set to `"public": false`. Output is `{"success": <bool>}`.
  * `remove_custom_course`: input is a JSON dictionary specifying the course to remove (`subject_id` is required). Output is `{"success": <bool>}`.

### Requirements

* `/requirements/list_reqs/` *(GET)*: Returns a dictionary where the keys are list IDs of requirements lists, and the values are metadata dictionaries containing various titles for the corresponding lists.

* `/requirements/get_json/<list_id>` *(GET)*: Use this endpoint to get a JSON representation of a course requirements list. The list_id should be one of the keys returned by `/requirements/list_reqs/`, or else a bad request error is thrown. The return value of this endpoint is a JSON representation which may contain the following keys:

  * `list-id` - the requirements list ID
  * `short-title` - a short title, e.g. "6-7"
  * `medium-title` - a medium title, e.g. "WGS Minor"
  * `title-no-degree` - a title without the degree name (e.g. "Computer Science and Engineering")
  * `title` - the full title (e.g. "Bachelor of Science in Computer Science and Engineering")
  * `desc` - an optional description of the statement or requirements list
  * `req` - string requirement, such as "6.009" or "24 units in 8.200-8.299" (if not present, see `reqs`)
  * `plain-string` - whether to interpret `req` as a parseable requirement ("6.009") or as a plain string ("24 units in 8.200-8.299"). Note that plain strings may have `(distinct-)threshold` keys attached, allowing the user to manually control progress.
  * `reqs` - a list of nested requirements statements (if not present, see req)
  * `connection-type` - logical connection type between the reqs (`all` or `any`, or `none` if it is a plain string)
  * `threshold` - optional dictionary describing the threshold to satisfy this statement. Keys are:
    * `type` - the type of inequality to apply (`LT`, `GT`, `LTE`, or `GTE`)
    * `cutoff` - the numerical cutoff
    * `criterion` - either `subjects` or `units`
  * `distinct-threshold` - optional dictionary describing the number of distinct child requirements of this statement that must be satisfied. Keys are the same as `threshold`.
  * `threshold-desc` - user-facing string describing the thresholds (if applicable)

* `/requirements/progress/`: Returns a JSON representation of a course requirements list, including user progresses. There are a few different ways to provide the user's courses and progress overrides to this endpoint:

  * `/requirements/progress/<list_id>/<courses>` *(GET)*: `courses` is a comma-separated list of subject IDs. (Progress overrides cannot be passed using this method. No authorization is necessary.)
  * `/requirements/progress/<list_id>?road=<road_id>` *(GET)*: `road_id` is the integer ID number of the user's road. The user must be logged in or an authorization token must be passed.
  * `/requirements/progress/<list_id>/` *(POST)*: The request body should contain the JSON representation of the road to evaluate against. (No authorization is necessary.)

  The JSON returned by this endpoint contains the following keys in addition to those defined above:

  * `fulfilled` - boolean indicating whether the requirement is completed
  * `progress` - the integer progress toward the requirement, in units of `criterion`
  * `max` - the maximum possible progress, serving as a denominator for `progress`
  * `percent_fulfilled` - the percentage fulfilled
  * `sat_courses` - a list of courses that satisfies this requirement

### Sync

* `/sync/roads/` *(GET)*: If a primary key is specified by the `id` query parameter, returns the contents of the given file as well as its last-modified agent. If no primary key is specified, returns a dictionary of primary-keys to metadata about each of the user's roads.

* `/sync/sync_road/` *(POST)*: This endpoint determines whether to change the remote copy of the file, update the local copy, or handle a sync conflict. The body of the request should be a JSON dictionary containing the following keys:

  * `id`: The primary key of the road to update (don't pass if adding a new file)
  * `contents`: The contents of the road to update
  * `changed`: The local last-modified date of the road
  * `downloaded`: The date of the last download of the road from the server
  * `name`: The road name (required if adding a new file, or if renaming an existing road)
  * `agent`: The name of the device submitting the change
  * `override`: Whether to override conflicts

  Returns a JSON dictionary that may update the above keys and/or add the following keys:

  * `success`: Whether the file was successfully compared against its remote version
  * `error`: A console error if `success` is false
  * `error_msg`: A user-facing error to display if `success` is false
  * `result`: A string indicating the result of the operation, e.g. "update_remote", "update_local", "conflict", or "no_change"
  * `other_name`, `other_agent`, `other_date`, `other_contents`, `this_agent`, `this_date`: Keys that are specified in the case of a conflict. In this case, the user should select whether to keep the local copy, the remote copy, or both. If keeping the local copy, the client should submit a new `sync_road` request with the `override` flag set to true.

* `/sync/delete_road/` *(POST)*: Deletes the file specified by the `id` key in the body of the request.

* `/sync/schedules`, `/sync/sync_schedule/`, `/sync/delete_schedule/`: Analogous to the above endpoints, but for schedules.
