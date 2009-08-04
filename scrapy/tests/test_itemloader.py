import unittest
import string

from scrapy.newitem.loader import ItemLoader, tree_expander
from scrapy.newitem.builder import reducers
from scrapy.newitem import Item, fields


class BaseItem(Item):
    name = fields.TextField()


class TestItem(BaseItem):
    url = fields.TextField()
    summary = fields.TextField()


class BaseItemLoader(ItemLoader):
    item_class = TestItem


class TestItemLoader(BaseItemLoader):
    expand_name = tree_expander(lambda v: v.title())


class DefaultedItemLoader(BaseItemLoader):
    expand = tree_expander(lambda v: v[:-1])


class InheritDefaultedItemLoader(DefaultedItemLoader):
    pass

class ListFieldTestItem(Item):
    names = fields.ListField(fields.TextField())


class ListFieldItemLoader(ItemLoader):
    item_class = ListFieldTestItem

    expand_names = tree_expander(lambda v: v.title())


class ItemLoaderTest(unittest.TestCase):

    def test_basic(self):
        ib = TestItemLoader()

        ib.add_value('name', u'marta')
        self.assertEqual(ib.get_value('name'), u'Marta')

        item = ib.get_item()
        self.assertEqual(item['name'], u'Marta')

    def test_multiple_functions(self):
        class TestItemLoader(BaseItemLoader):
            expand_name = tree_expander(lambda v: v.title(), lambda v: v[:-1])

        ib = TestItemLoader()

        ib.add_value('name', u'marta')
        self.assertEqual(ib.get_value('name'), u'Mart')

        item = ib.get_item()
        self.assertEqual(item['name'], u'Mart')

    def test_defaulted(self):
        dib = DefaultedItemLoader()

        dib.add_value('name', u'marta')
        self.assertEqual(dib.get_value('name'), u'mart')

    def test_inherited_default(self):
        dib = InheritDefaultedItemLoader()

        dib.add_value('name', u'marta')
        self.assertEqual(dib.get_value('name'), u'mart')

    def test_inheritance(self):
        class ChildItemLoader(TestItemLoader):
            expand_url = tree_expander(lambda v: v.lower())

        ib = ChildItemLoader()

        ib.add_value('url', u'HTTP://scrapy.ORG')
        self.assertEqual(ib.get_value('url'), u'http://scrapy.org')

        ib.add_value('name', u'marta')
        self.assertEqual(ib.get_value('name'), u'Marta')

        class ChildChildItemLoader(ChildItemLoader):
            expand_url = tree_expander(lambda v: v.upper())
            expand_summary = tree_expander(lambda v: v)

        ib = ChildChildItemLoader()

        ib.add_value('url', u'http://scrapy.org')
        self.assertEqual(ib.get_value('url'), u'HTTP://SCRAPY.ORG')

        ib.add_value('name', u'marta')
        self.assertEqual(ib.get_value('name'), u'Marta')

    def test_multiplevaluedadaptor(self):
        ib = ListFieldItemLoader()

        ib.add_value('names',  [u'name1', u'name2'])
        self.assertEqual(ib.get_value('names'), [u'Name1', u'Name2'])

    def test_identity(self):
        class IdentityDefaultedItemLoader(DefaultedItemLoader):
            expand_name = tree_expander()

        ib = IdentityDefaultedItemLoader()

        ib.add_value('name', u'marta')
        self.assertEqual(ib.get_value('name'), u'marta')

    def test_staticmethods(self):
        class ChildItemLoader(TestItemLoader):
            expand_name = tree_expander(TestItemLoader.expand_name, string.swapcase)

        ib = ChildItemLoader()

        ib.add_value('name', u'marta')
        self.assertEqual(ib.get_value('name'), u'mARTA')


    def test_staticdefaults(self):
        class ChildDefaultedItemLoader(DefaultedItemLoader):
            expand_name = tree_expander(DefaultedItemLoader.expand, string.swapcase)

        ib = ChildDefaultedItemLoader()

        ib.add_value('name', u'marta')
        self.assertEqual(ib.get_value('name'), u'MART')

    def test_reducer(self):
        ib = TestItemLoader()

        ib.add_value('name', [u'mar', u'ta'])
        self.assertEqual(ib.get_value('name'), u'Mar Ta')

        class TakeFirstItemLoader(TestItemLoader):
            reduce_name = staticmethod(reducers.take_first)

        ib = TakeFirstItemLoader()

        ib.add_value('name', [u'mar', u'ta'])
        self.assertEqual(ib.get_value('name'), u'Mar')

    def test_loader_args(self):
        def expander_func_with_args(value, loader_args):
            if 'val' in loader_args:
                return loader_args['val']
            return value

        class ChildItemLoader(TestItemLoader):
            expand_url = tree_expander(expander_func_with_args)

        ib = ChildItemLoader(val=u'val')
        ib.add_value('url', u'text')
        self.assertEqual(ib.get_value('url'), 'val')

        ib = ChildItemLoader()
        ib.add_value('url', u'text', val=u'val')
        self.assertEqual(ib.get_value('url'), 'val')

    def test_add_value_unknown_field(self):
        ib = TestItemLoader()
        ib.add_value('wrong_field', [u'lala', u'lolo'])

        self.assertRaises(KeyError, ib.get_item)
