#!/usr/bin/env python
# coding: utf-8

# Copyright (c) Saga Inc.
# Distributed under the terms of the GPL License.
"""
Exports the transpile function, which takes the backend widget
container and generates transpiled Python code.
"""

from typing import Any, Dict, List
from mitosheet.array_utils import deduplicate_array
from mitosheet.code_chunks.code_chunk import CodeChunk
from mitosheet.code_chunks.code_chunk_utils import get_code_chunks
from mitosheet.code_chunks.postprocessing import POSTPROCESSING_CODE_CHUNKS

from mitosheet.preprocessing import PREPROCESS_STEP_PERFORMERS
from mitosheet.transpiler.transpile_utils import convert_script_to_function
from mitosheet.types import StepsManagerType


IN_PREVIOUS_STEP_COMMENT = '# You\'re viewing a previous step. Click fast forward in the Mitosheet above to see the full analysis.'


IMPORT_STATEMENTS = {
    1: 'from mitosheet.public.v1 import *',
    2: 'from mitosheet.public.v2 import *',
    3: 'from mitosheet.public.v3 import *'
}

def transpile(
        steps_manager: StepsManagerType, 
        add_comments: bool=True,
        optimize: bool=True
    ) -> List[str]:
    """
    Transpiles the code from the current steps in the steps_manager, 
    displaying up to the checked out step.

    If add_comments, then adds descriptive comments using the step 
    describe functions. 
    """

    imports_code: List[str] = []
    code: List[str] = []

    # First, we transpile all the preprocessing steps
    for preprocess_step_performer in PREPROCESS_STEP_PERFORMERS:
        preprocess_code, preprocess_imports = preprocess_step_performer.transpile(
            steps_manager,
            steps_manager.preprocess_execution_data[preprocess_step_performer.preprocess_step_type()],
        )
        if len(preprocess_code) > 0:
            code.extend(preprocess_code)
            code.append('')

        imports_code.extend(preprocess_imports)

    # We only transpile up to the currently checked out step
    all_code_chunks: List[CodeChunk] = get_code_chunks(steps_manager.steps_including_skipped[:steps_manager.curr_step_idx + 1], optimize=optimize)

    # We also make sure to include all the post_processing code chunks, which are those
    # code chunks that are always at the end of the dataframe
    for postprocessing_code_chunk in POSTPROCESSING_CODE_CHUNKS:
        all_code_chunks.append(postprocessing_code_chunk(steps_manager.curr_step.initial_defined_state, steps_manager.curr_step.final_defined_state))

    for code_chunk in all_code_chunks:
        comment = '# ' + code_chunk.get_description_comment().strip().replace('\n', '\n# ')
        (gotten_code, code_chunk_imports) = code_chunk.get_code()

        # Make sure to not generate comments or code for steps with no code 
        if len(gotten_code) > 0:
            if add_comments:
                gotten_code.insert(0, comment)
            code.extend(gotten_code)

            # Then add a line of whitespace
            code.append('')

        imports_code.extend(code_chunk_imports)

    # If we have a historical step checked out, then we add a comment letting
    # the user know this is the case
    if steps_manager.curr_step_idx != len(steps_manager.steps_including_skipped) - 1:
        code.append(IN_PREVIOUS_STEP_COMMENT)

    # We then deduplicate the imports, keeping the same order as originally
    final_imports_code = deduplicate_array(imports_code)

    # We then add the import statement for the correct version of mitosheet
    if len(code) > 0:
        final_imports_code.insert(0, IMPORT_STATEMENTS[steps_manager.public_interface_version])

    # If we should transpile this as a function, we do so
    if steps_manager.code_options['as_function']:
        final_code = convert_script_to_function(
            steps_manager,
            final_imports_code,
            code,
            steps_manager.code_options['function_name'],
            steps_manager.code_options['function_params']
        )
        return final_code

    # We add some whitespace if there are imports
    if len(final_imports_code) > 0:
        final_imports_code.append('')

    return final_imports_code + code
