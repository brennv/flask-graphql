# Flask-GraphQL

[![Build Status](https://travis-ci.org/graphql-python/flask-graphql.svg?branch=master)](https://travis-ci.org/graphql-python/flask-graphql) [![Coverage Status](https://coveralls.io/repos/graphql-python/graphql-flask/badge.svg?branch=master&service=github)](https://coveralls.io/github/graphql-python/graphql-flask?branch=master) [![PyPI version](https://badge.fury.io/py/graphql-flask.svg)](https://badge.fury.io/py/graphql-flask)

Adds GraphQL support to your Flask application.

## Usage

Just use the `GraphQLView` view from `flask_graphql`

```python
from flask_graphql import GraphQLView

app.add_url_rule('/graphql', view_func=GraphQLView.as_view('graphql', schema=schema, graphiql=True))

```

This will add `/graphql` and `/graphiql` endpoints to your app.

### Supported options
 * `schema`: The `GraphQLSchema` object that you want the view to execute when it gets a valid request.
 * `context`: A value to pass as the `context` to the `graphql()` function.
 * `root_value`: The `root_value` you want to provide to `executor.execute`.
 * `pretty`: Whether or not you want the response to be pretty printed JSON.
 * `executor`: The `Executor` that you want to use to execute queries.
 * `graphiql`: If `True`, may present [GraphiQL](https://github.com/graphql/graphiql) when loaded directly
    from a browser (a useful tool for debugging and exploration).

You can also subclass `GraphQLView` and overwrite `get_root_value(self, request)` to have a dynamic root value
per request.

```python
class UserRootValue(GraphQLView):
    def get_root_value(self, request):
        return request.user

```
