import re

from rest_framework.pagination import PageNumberPagination


class WebApiPageNumberPagination(PageNumberPagination):
    page_size = 5
    page_size_query_param = 'page_size'

    def get_next_link(self):
        url = super().get_next_link()
        # if url is not None:
        #     url = re.sub('[?&]uts=\d+', '', url)  # strip useless uts params
        return url

    def get_previous_link(self):
        url = super().get_previous_link()
        # if url is not None:
        #     url = re.sub('[?&]uts=\d+', '', url)  # strip useless uts params
        return url
