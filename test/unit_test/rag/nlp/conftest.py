#
#  Copyright 2024 The InfiniFlow Authors. All Rights Reserved.
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#

"""
Mock common.settings so rag_tokenizer tests run without infrastructure.
"""

import sys
from unittest.mock import MagicMock

_modules_to_mock = [
    "common",
    "common.settings",
    "common.token_utils",
    "common.connection_utils",
    "common.doc_store",
    "common.doc_store.doc_store_base",
]

for mod_name in _modules_to_mock:
    if mod_name not in sys.modules:
        sys.modules[mod_name] = MagicMock()

# Default: use Elasticsearch engine (not Infinity), so tokenize() runs real logic
sys.modules["common.settings"].DOC_ENGINE_INFINITY = False
# Provide a basic num_tokens_from_string stub
sys.modules["common.token_utils"].num_tokens_from_string = lambda text, model="": len(text.split())
