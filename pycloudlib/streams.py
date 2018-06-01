# This file is part of pycloudlib. See LICENSE file for license information.
"""Wrapper class around Simplestreams."""
import logging

from simplestreams import filters, mirrors
from simplestreams import util as s_util


class Streams(object):
    """Streams Class."""

    def __init__(self, mirror_url, keyring_path):
        """Initialize Steams Class."""
        self._log = logging.getLogger(__name__)
        self.mirror_url = mirror_url
        self.keyring_path = keyring_path

    def query(self, img_filter, max_results=None):
        """Query streams for latest image given a specific filter.

        Args:
            img_conf: configuration for image
            filters: array of filters as strings format 'key=value'

        Returns:
            dictionary with latest image information or empty

        """
        def policy(content, path):  # pylint: disable=W0613
            """TODO."""
            return s_util.read_signed(content, keyring=self.keyring_path)

        (url, path) = s_util.path_from_mirror_url(self.mirror_url, None)
        s_mirror = mirrors.UrlMirrorReader(url, policy=policy)

        config = {'filters': filters.get_filters(img_filter)}
        if max_results:
            config['max_items'] = max_results

        self._log.debug('streams using following config %s', config)
        t_mirror = FilterMirror(config)
        t_mirror.sync(s_mirror, path)

        return t_mirror.json_entries


class FilterMirror(mirrors.BasicMirrorWriter):
    """Taken from sstream-query to return query result as json array."""

    def __init__(self, config=None):
        """Initialize custom Filter Mirror class.

        Args:
            config: custom config to use
        """
        super(FilterMirror, self).__init__(config=config)
        if config is None:
            config = {}
        self.config = config
        self.filters = config.get('filters', [])
        self.json_entries = []

    def load_products(self, path=None, content_id=None):
        """Load each product.

        Args:
            path: path the product
            content_id: ID of product

        Returns:
            dictionary of products

        """
        return {'content_id': content_id, 'products': {}}

    def filter_item(self, data, src, target, pedigree):
        """Filter items based on filter.

        Args:
            data: TBD
            src: TBD
            target: TBD
            pedigree: TBD

        Returns:
            Filtered items

        """
        return filters.filter_item(self.filters, data, src, pedigree)

    def insert_item(self, data, src, target, pedigree, contentsource):
        """Insert item received.

        src and target are top level products:1.0
        data is src['products'][ped[0]]['versions'][ped[1]]['items'][ped[2]]
        contentsource is a ContentSource if 'path' exists in data or None

        Args:
            data: Data from simplestreams
            src: TBD
            target: TBD
            pedigree: TBD
            contentsource: TBD
        """
        data = s_util.products_exdata(src, pedigree)
        if 'path' in data:
            data.update({'item_url': contentsource.url})
        self.json_entries.append(data)
