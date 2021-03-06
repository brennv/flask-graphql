import json

import six
from flask import Response, request
from flask.views import View
from werkzeug.exceptions import BadRequest, MethodNotAllowed

from graphql import Source, execute, parse, validate
from graphql.error import format_error as format_graphql_error
from graphql.error import GraphQLError
from graphql.execution import ExecutionResult
from graphql.type.schema import GraphQLSchema
from graphql.utils.get_operation_ast import get_operation_ast

from .render_graphiql import render_graphiql


class HttpError(Exception):
    def __init__(self, response, message=None, *args, **kwargs):
        self.response = response
        self.message = message = message or response.description
        super(HttpError, self).__init__(message, *args, **kwargs)


class GraphQLView(View):
    schema = None
    executor = None
    root_value = None
    context = None
    pretty = False
    graphiql = False
    graphiql_version = None

    methods = ['GET', 'POST', 'PUT', 'DELETE']

    def __init__(self, **kwargs):
        super(GraphQLView, self).__init__()
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)

        inner_schema = getattr(self.schema, 'schema', None)
        if not self.executor:
            self.executor = getattr(self.schema, 'executor', None)

        if inner_schema:
            self.schema = inner_schema

        assert isinstance(self.schema, GraphQLSchema), 'A Schema is required to be provided to GraphQLView.'

    # noinspection PyUnusedLocal
    def get_root_value(self, request):
        return self.root_value

    def get_context(self, request):
        return request

    def dispatch_request(self):
        try:
            if request.method.lower() not in ('get', 'post'):
                raise HttpError(MethodNotAllowed(['GET', 'POST'], 'GraphQL only supports GET and POST requests.'))

            data = self.parse_body(request)
            show_graphiql = self.graphiql and self.can_display_graphiql(data)

            query, variables, operation_name = self.get_graphql_params(request, data)

            execution_result = self.execute_graphql_request(
                data,
                query,
                variables,
                operation_name,
                show_graphiql
            )

            if execution_result:
                response = {}

                if execution_result.errors:
                    response['errors'] = [self.format_error(e) for e in execution_result.errors]

                if execution_result.invalid:
                    status_code = 400
                else:
                    status_code = 200
                    response['data'] = execution_result.data

                result = self.json_encode(request, response)
            else:
                result = None

            if show_graphiql:
                return render_graphiql(
                    graphiql_version=self.graphiql_version,
                    query=query,
                    variables=variables,
                    operation_name=operation_name,
                    result=result
                )

            return Response(
                status=status_code,
                response=result,
                content_type='application/json'
            )

        except HttpError as e:
            return Response(
                self.json_encode(request, {
                    'errors': [self.format_error(e)]
                }),
                status=e.response.code,
                headers={'Allow': ['GET, POST']},
                content_type='application/json'
            )

    def json_encode(self, request, d):
        if not self.pretty and not request.args.get('pretty'):
            return json.dumps(d, separators=(',', ':'))

        return json.dumps(d, sort_keys=True,
                          indent=2, separators=(',', ': '))

    # noinspection PyBroadException
    def parse_body(self, request):
        content_type = self.get_content_type(request)
        if content_type == 'application/graphql':
            return {'query': request.data.decode()}

        elif content_type == 'application/json':
            try:
                request_json = json.loads(request.data.decode('utf8'))
                assert isinstance(request_json, dict)
                return request_json
            except:
                raise HttpError(BadRequest('POST body sent invalid JSON.'))

        elif content_type == 'application/x-www-form-urlencoded':
            return request.form

        elif content_type == 'multipart/form-data':
            return request.form

        return {}

    def execute(self, *args, **kwargs):
        return execute(self.schema, *args, **kwargs)

    def execute_graphql_request(self, data, query, variables, operation_name, show_graphiql=False):
        if not query:
            if show_graphiql:
                return None
            raise HttpError(BadRequest('Must provide query string.'))

        try:
            source = Source(query, name='GraphQL request')
            ast = parse(source)
            validation_errors = validate(self.schema, ast)
            if validation_errors:
                return ExecutionResult(
                    errors=validation_errors,
                    invalid=True,
                )
        except Exception as e:
            return ExecutionResult(errors=[e], invalid=True)

        if request.method.lower() == 'get':
            operation_ast = get_operation_ast(ast, operation_name)
            if operation_ast and operation_ast.operation != 'query':
                if show_graphiql:
                    return None
                raise HttpError(MethodNotAllowed(
                    ['POST'], 'Can only perform a {} operation from a POST request.'.format(operation_ast.operation)
                ))

        try:
            return self.execute(
                ast,
                root_value=self.get_root_value(request),
                variable_values=variables or {},
                operation_name=operation_name,
                context_value=self.get_context(request),
                executor=self.executor
            )
        except Exception as e:
            return ExecutionResult(errors=[e], invalid=True)

    @classmethod
    def can_display_graphiql(cls, data):
        raw = 'raw' in request.args or 'raw' in data
        return not raw and cls.request_wants_html(request)

    @classmethod
    def request_wants_html(cls, request):
        best = request.accept_mimetypes \
            .best_match(['application/json', 'text/html'])
        return best == 'text/html' and \
            request.accept_mimetypes[best] > \
            request.accept_mimetypes['application/json']

    @staticmethod
    def get_graphql_params(request, data):
        query = request.args.get('query') or data.get('query')
        variables = request.args.get('variables') or data.get('variables')

        if variables and isinstance(variables, six.text_type):
            try:
                variables = json.loads(variables)
            except:
                raise HttpError(BadRequest('Variables are invalid JSON.'))

        operation_name = request.args.get('operationName') or data.get('operationName')

        return query, variables, operation_name

    @staticmethod
    def format_error(error):
        if isinstance(error, GraphQLError):
            return format_graphql_error(error)

        return {'message': six.text_type(error)}

    @staticmethod
    def get_content_type(request):
        # We use mimetype here since we don't need the other
        # information provided by content_type
        return request.mimetype
