# Copyright 2017 Neural Networks and Deep Learning lab, MIPT
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from logging import getLogger
from typing import List, Optional, Union, Tuple

import re
from hdt import HDTDocument

from deeppavlov.core.commands.utils import expand_path
from deeppavlov.core.common.registry import register
from deeppavlov.core.models.component import Component


log = getLogger(__name__)


@register('wiki_parser')
class WikiParser(Component):
    """This class extract relations, objects or triplets from Wikidata HDT file"""

    def __init__(self, wiki_filename: str, **kwargs):
        log.debug(f'__init__ wiki_filename: {wiki_filename}')
        wiki_path = expand_path(wiki_filename)
        self.document = HDTDocument(str(wiki_path))

    def __call__(self, what_return: List[str],
                 query_seq: List[Tuple[str]],
                 filter_entities: Optional[List[Tuple[str]]] = None,
                 order_info: Optional[Tuple[str, str]] = None) -> Union[str, List[str]]:
        
        extended_combs = []
        combs = []
        for n, query in enumerate(query_seq):
            unknown_elem_positions = [(pos, elem) for pos, elem in enumerate(query) if elem.startswith('?')]
            if n == 0:
                combs = self.search(query, unknown_elem_positions)
            else:
                if combs:
                    known_elements = []
                    extended_combs = []
                    for elem in query:
                        if elem in combs[0].keys():
                            known_elements.append(elem)
                    for comb in combs:
                        known_values = [comb[known_elem] for known_elem in known_elements]
                        for known_elem, known_value in zip(known_elements, known_values):
                            filled_query = [elem.replace(known_elem, known_value) for elem in query]
                            new_combs = self.search(filled_query, unknown_elem_positions)
                            for new_comb in new_combs:
                                extended_combs.append({**comb, **new_comb})
                combs = extended_combs
        
        if combs:
            if filter_entities:
                print("filter_entities", filter_entities)
                for filter_entity in filter_entities:
                    filter_elem, filter_value = filter_entity
                    print("elem, value", filter_elem, filter_value)
                    print("combs", combs[0])
                    combs = [comb for comb in combs if filter_value in comb[filter_elem]]

            if order_info.variable is not None:
                reverse = True if order_info.sorting_order == "DESC" else False
                sort_elem = order_info.variable
                print("order_info", order_info, "reverse", reverse)
                print("combs", combs[0])
                combs = sorted(combs, key=lambda x: float(x[sort_elem].split('^^')[0].strip('"')), reverse=reverse)
                combs = [combs[0]]
            
            if what_return[-1].startswith("COUNT"):
                combs = [[combs[0][key] for key in what_return[:-1]] + [len(combs)]]
            else:
                combs = [[elem[key] for key in what_return] for elem in combs]

        return combs

    def search(self, query, unknown_elem_positions):
        query = list(map(lambda elem: "" if elem.startswith('?') else elem, query))
        subj, rel, obj = query
        triplets, c = self.document.search_triples(subj, rel, obj)
        combs = [{elem: triplet[pos] for pos, elem in unknown_elem_positions} for triplet in triplets]
        return combs
        

    def find_label(self, entity):
        print("find label", entity)
        entity = str(entity).replace('"', '')
        if entity.startswith("Q"):
            entity = "http://www.wikidata.org/entity/" + entity

        if entity.startswith("http://www.wikidata.org/entity/"):
            labels, cardinality = self.document.search_triples(entity, "http://www.w3.org/2000/01/rdf-schema#label", "")
            for label in labels:
                if label[2].endswith("@en"):
                    found_label = label[2].strip('@en').replace('"', '')
                    return found_label

        elif entity.endswith("@en"):
            entity = entity.strip('@en', '')
            return entity

        elif "^^" in entity:
            entity = entity.split("^^")[0]
            for token in ["T00:00:00Z", "+"]:
                entity = entity.replace(token, '')
            return entity

        elif entity.isdigit():
            return entity

        return "Not Found"

    def find_alias(self, entity):
        aliases = []
        if entity.startswith("http://www.wikidata.org/entity/"):
            labels, cardinality = self.document.search_triples(entity,
                                                   "http://www.w3.org/2004/02/skos/core#altLabel", "")
            aliases = [label[2].strip('@en').strip('"') for label in labels if label[2].endswith("@en")]
        return aliases

    def find_rels(self, entity, direction, rel_type = None):
        if direction == "forw":
            triplets, num = self.document.search_triples(f"http://www.wikidata.org/entity/{entity}", "", "")
        else:
            triplets, num = self.document.search_triples("", "", f"http://www.wikidata.org/entity/{entity}")
        
        if rel_type is not None:
            start_str = f"http://www.wikidata.org/prop/{rel_type}"
        else:
            start_str = "http://www.wikidata.org/prop/P"
        rels = [triplet[1] for triplet in triplets if triplet[1].startswith(start_str)]
        return rels
