from rest_framework import pagination
from rest_framework.response import Response
from collections import OrderedDict


class StandardResultsPagination(pagination.PageNumberPagination):
    page_size = 12
    page_size_query_param = 'page_size'
    max_page_size = 100

    def get_paginated_response(self, data):
        result = OrderedDict([
            ('count', self.page.paginator.num_pages),
            ('next', self.get_next_link()),
            ('current', self.page.number),
            ('previous', self.get_previous_link()),
            ('page_size', self.get_page_size(self.request)),
            ('results', data)
        ])
        return Response(result)

    def get_next_link(self):
        if not self.page.has_next():
            return None
        page_number = self.page.next_page_number()
        return page_number

    def get_previous_link(self):
        if not self.page.has_previous():
            return None
        page_number = self.page.previous_page_number()
        return page_number
