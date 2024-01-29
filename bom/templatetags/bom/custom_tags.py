# custom_tags.py

from django import template

register = template.Library()

@register.inclusion_tag('bom/recursive_nodes.html')
def recursetree(nodes):
    return {'nodes': nodes}
