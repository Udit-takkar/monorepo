#!/usr/bin/env python
# coding: utf-8

# Copyright (c) Saga Inc.
# Distributed under the terms of the GPL License.
import os
from mitosheet.transpiler.transpile_utils import NEWLINE_TAB, TAB
import pytest
import pandas as pd

from mitosheet.api.get_parameterizable_params import get_parameterizable_params
from mitosheet.transpiler.transpile import transpile
from mitosheet.tests.test_utils import create_mito_wrapper_with_data, create_mito_wrapper
from mitosheet.tests.decorators import pandas_post_1_2_only, python_post_3_6_only

def test_transpile_single_column():
    mito = create_mito_wrapper_with_data(['abc'])
    mito.set_formula('=A', 0, 'B', add_column=True)

    assert mito.transpiled_code == [
        'from mitosheet.public.v3 import *',
        '',
        "df1.insert(1, 'B', df1[\'A\'])", 
        ''
    ]


def test_transpile_multiple_columns_no_relationship():
    mito = create_mito_wrapper_with_data(['abc'])
    mito.add_column(0, 'B')
    mito.add_column(0, 'C')
    print(mito.transpiled_code)
    assert mito.transpiled_code == [
        'from mitosheet.public.v3 import *',
        '',
        'df1.insert(1, \'B\', 0)', 
        '',
        'df1.insert(2, \'C\', 0)', 
        ''
    ]

def test_transpile_columns_in_each_sheet():
    mito = create_mito_wrapper_with_data(['abc'], sheet_two_A_data=['abc'])
    mito.add_column(0, 'B')
    mito.add_column(1, 'B')

    assert mito.transpiled_code == [
        'from mitosheet.public.v3 import *',
        '',
        'df1.insert(1, \'B\', 0)',
        '',
        'df2.insert(1, \'B\', 0)',
        ''
    ]

def test_transpile_multiple_columns_linear():
    mito = create_mito_wrapper_with_data(['abc'])
    mito.set_formula('=A', 0, 'B', add_column=True)
    mito.set_formula('=B', 0, 'C', add_column=True)

    assert mito.transpiled_code == [
        'from mitosheet.public.v3 import *',
        '',
        'df1.insert(1, \'B\', df1[\'A\'])',
        '',
        'df1.insert(2, \'C\', df1[\'B\'])',
        '',
    ]

COLUMN_HEADERS = [
    ('ABC'),
    ('ABC_D'),
    ('ABC_DEF'),
    ('ABC_123'),
    ('ABC_HAHA_123'),
    ('ABC_HAHA-123'),
    ('---data---'),
    ('---da____ta---'),
    ('--'),
]
@pytest.mark.parametrize("column_header", COLUMN_HEADERS)
def test_transpile_column_headers_non_alphabet(column_header):
    mito = create_mito_wrapper_with_data(['abc'])
    mito.set_formula('=A', 0, column_header, add_column=True)

    assert mito.transpiled_code == [
        'from mitosheet.public.v3 import *',
        '',
        f'df1.insert(1, \'{column_header}\', df1[\'A\'])', 
        '',
    ]


COLUMN_HEADERS = [
    ('ABC'),
    ('ABC_D'),
    ('ABC_DEF'),
    ('ABC_123'),
    ('ABC_HAHA_123'),
    ('ABC_HAHA-123'),
    ('---data---'),
    ('---da____ta---'),
    ('--'),
]
@pytest.mark.parametrize("column_header", COLUMN_HEADERS)
def test_transpile_column_headers_non_alphabet_multi_sheet(column_header):
    mito = create_mito_wrapper_with_data(['abc'], sheet_two_A_data=['abc'])
    mito.set_formula('=A', 0, column_header, add_column=True)
    mito.set_formula('=A', 1, column_header, add_column=True)

    assert mito.transpiled_code == [
        'from mitosheet.public.v3 import *',
        '',
        f'df1.insert(1, \'{column_header}\', df1[\'A\'])', 
        '',
        f'df2.insert(1, \'{column_header}\', df2[\'A\'])', 
        '',
    ]

def test_preserves_order_columns():
    mito = create_mito_wrapper_with_data(['abc'])
    # Topological sort will currently display this in C, B order
    mito.add_column(0, 'B')
    mito.add_column(0, 'C')

    assert mito.transpiled_code == [
        'from mitosheet.public.v3 import *',
        '',
        'df1.insert(1, \'B\', 0)',
        '',
        'df1.insert(2, \'C\', 0)',
        '',
    ]

def test_transpile_delete_columns():
    df1 = pd.DataFrame(data={'A': [1], 'B': [101], 'C': [11]})
    mito = create_mito_wrapper(df1)
    mito.delete_columns(0, ['C', 'B'])

    assert mito.transpiled_code == [
        'from mitosheet.public.v3 import *',
        '',
        'df1.drop([\'C\', \'B\'], axis=1, inplace=True)',
        '',
    ]


# TESTING OPTIMIZATION

def test_removes_unedited_formulas_for_unedited_sheets():
    df1 = pd.DataFrame(data={'A': [1], 'B': [101], 'C': [11]})
    df2 = pd.DataFrame(data={'A': [1], 'B': [101], 'C': [11]})
    mito = create_mito_wrapper(df1, df2)

    mito.set_formula('=C', 0, 'D', add_column=True)
    mito.set_formula('=C', 1, 'D', add_column=True)

    mito.merge_sheets('lookup', 0, 1, [['A', 'A']], ['A', 'B', 'C', 'D'], ['A', 'B', 'C', 'D'])

    mito.set_formula('=C + 1', 1, 'D', add_column=True)

    assert mito.transpiled_code == [
        'from mitosheet.public.v3 import *',
        '',
        "df1.insert(3, 'D', df1[\'C\'])", 
        '',
        "df2.insert(3, 'D', df2[\'C\'])", 
        '',
        'temp_df = df2.drop_duplicates(subset=[\'A\']) # Remove duplicates so lookup merge only returns first match', 
        'df3 = df1.merge(temp_df, left_on=[\'A\'], right_on=[\'A\'], how=\'left\', suffixes=[\'_df1\', \'_df2\'])',
        '',
        'df2[\'D\'] = df2[\'C\'] + 1',
        '',
    ]


def test_mulitple_merges_no_formula_steps():
    df1 = pd.DataFrame(data={'A': [1], 'B': [101], 'C': [11]})
    df2 = pd.DataFrame(data={'A': [1], 'B': [101], 'C': [11]})
    mito = create_mito_wrapper(df1, df2)
    mito.merge_sheets('lookup', 0, 1, [['A', 'A']], ['A', 'B', 'C'], ['A', 'B', 'C'])
    mito.merge_sheets('lookup', 0, 1, [['A', 'A']], ['A', 'B', 'C'], ['A', 'B', 'C'])
    mito.merge_sheets('lookup', 0, 1, [['A', 'A']], ['A', 'B', 'C'], ['A', 'B', 'C'])


    assert mito.transpiled_code == [
        'from mitosheet.public.v3 import *',
        '',
        'temp_df = df2.drop_duplicates(subset=[\'A\']) # Remove duplicates so lookup merge only returns first match', 
        'df3 = df1.merge(temp_df, left_on=[\'A\'], right_on=[\'A\'], how=\'left\', suffixes=[\'_df1\', \'_df2\'])',
        '',
        'temp_df = df2.drop_duplicates(subset=[\'A\']) # Remove duplicates so lookup merge only returns first match', 
        'df4 = df1.merge(temp_df, left_on=[\'A\'], right_on=[\'A\'], how=\'left\', suffixes=[\'_df1\', \'_df2\'])',
        '',
        'temp_df = df2.drop_duplicates(subset=[\'A\']) # Remove duplicates so lookup merge only returns first match', 
        'df5 = df1.merge(temp_df, left_on=[\'A\'], right_on=[\'A\'], how=\'left\', suffixes=[\'_df1\', \'_df2\'])',
        '',
    ]

def test_optimization_with_other_edits():
    df1 = pd.DataFrame(data={'A': [1], 'B': [101], 'C': [11]})
    df2 = pd.DataFrame(data={'A': [1], 'B': [101], 'C': [11]})
    mito = create_mito_wrapper(df1, df2)
    mito.add_column(0, 'D')
    mito.set_formula('=A', 0, 'D')
    mito.merge_sheets('lookup', 0, 1, [['A', 'A']], ['A', 'B', 'C', 'D'], ['A', 'B', 'C'])
    mito.add_column(0, 'AAA')
    mito.delete_columns(0, ['AAA'])

    assert mito.transpiled_code == [
        'from mitosheet.public.v3 import *',
        '',
        "df1.insert(3, 'D', df1[\'A\'])", 
        '',
        'temp_df = df2.drop_duplicates(subset=[\'A\']) # Remove duplicates so lookup merge only returns first match', 
        'df3 = df1.merge(temp_df, left_on=[\'A\'], right_on=[\'A\'], how=\'left\', suffixes=[\'_df1\', \'_df2\'])',
        '',
    ]


def test_transpile_does_no_initial():
    df1 = pd.DataFrame(data={'First Name': ['Nate', 'Nate'], 123: ['Rush', 'Jack'], True: ['1', '2']})
    mito = create_mito_wrapper(df1)

    assert len(mito.transpiled_code) == 0

    
def test_transpile_reorder_column():
    df1 = pd.DataFrame(data={'A': ['aaron'], 'B': ['jon']})
    mito = create_mito_wrapper(df1)
    mito.reorder_column(0, 'A', 1)

    assert mito.transpiled_code == [
        'from mitosheet.public.v3 import *',
        '',
        'df1_columns = [col for col in df1.columns if col != \'A\']',
        'df1_columns.insert(1, \'A\')',
        'df1 = df1[df1_columns]',
        '',
    ]

def test_transpile_two_column_reorders():
    df1 = pd.DataFrame(data={'A': ['aaron'], 'B': ['jon']})
    mito = create_mito_wrapper(df1)
    mito.reorder_column(0, 'A', 1)
    mito.reorder_column(0, 'B', 1)

    assert mito.transpiled_code == [
        'from mitosheet.public.v3 import *',
        '',
        'df1_columns = [col for col in df1.columns if col != \'A\']',
        'df1_columns.insert(1, \'A\')',
        'df1 = df1[df1_columns]',
        '',
        'df1_columns = [col for col in df1.columns if col != \'B\']',
        'df1_columns.insert(1, \'B\')',
        'df1 = df1[df1_columns]',
        '',
    ]

def test_transpile_reorder_column_invalid():
    df1 = pd.DataFrame(data={'A': ['aaron'], 'B': ['jon']})
    mito = create_mito_wrapper(df1)
    mito.reorder_column(0, 'A', 5)

    assert mito.transpiled_code == [
        'from mitosheet.public.v3 import *',
        '',
        'df1_columns = [col for col in df1.columns if col != \'A\']',
        'df1_columns.insert(1, \'A\')',
        'df1 = df1[df1_columns]',
        '',
    ]

def test_transpile_merge_then_sort():
    df1 = pd.DataFrame(data={'Name': ["Aaron", "Nate"], 'Number': [123, 1]})
    df2 = pd.DataFrame(data={'Name': ["Aaron", "Nate"], 'Sign': ['Gemini', "Tarus"]})
    mito = create_mito_wrapper(df1, df2)
    mito.merge_sheets('lookup', 0, 1, [['Name', 'Name']], list(df1.keys()), list(df2.keys()))
    mito.sort(2, 'Number', 'ascending')

    assert mito.transpiled_code == [
        'from mitosheet.public.v3 import *',
        '',
        'temp_df = df2.drop_duplicates(subset=[\'Name\']) # Remove duplicates so lookup merge only returns first match',
        'df3 = df1.merge(temp_df, left_on=[\'Name\'], right_on=[\'Name\'], how=\'left\', suffixes=[\'_df1\', \'_df2\'])',
        '',
        'df3 = df3.sort_values(by=\'Number\', ascending=True, na_position=\'first\')',
        '',
    ]

def test_transpile_multiple_pandas_imports_combined(tmp_path):
    tmp_file = str(tmp_path / 'txt.csv')
    df1 = pd.DataFrame(data={'Name': ["Aaron", "Nate"], 'Number': [123, 1]})
    df1.to_csv(tmp_file, index=False)
    mito = create_mito_wrapper(df1)
    mito.simple_import([tmp_file])
    mito.add_column(0, 'A', -1)
    mito.simple_import([tmp_file])
    mito.add_column(1, 'A', -1)
    mito.simple_import([tmp_file])

    assert len(mito.optimized_code_chunks) == 5
    assert 'import pandas as pd' in mito.transpiled_code
    assert len([c for c in mito.transpiled_code if c == 'import pandas as pd']) == 1

def test_transpile_as_function_no_params(tmp_path):
    tmp_file = str(tmp_path / 'txt.csv')
    df1 = pd.DataFrame({'A': [1], 'B': [2]})
    df1.to_csv(tmp_file, index=False)

    mito = create_mito_wrapper()
    mito.simple_import([tmp_file])
    mito.code_options_update({'as_function': True, 'function_name': 'function', 'function_params': {}})

    print(mito.transpiled_code)

    assert mito.transpiled_code == [
        'from mitosheet.public.v3 import *',
        "import pandas as pd",
        "",
        "def function():",
        f"{TAB}txt = pd.read_csv(r'{tmp_file}')",
        f'{TAB}',
        f"{TAB}return txt",
        "",
        "txt = function()"
    ]

def test_transpile_as_function_df_params():
    mito = create_mito_wrapper(pd.DataFrame({'A': [1]}), arg_names=['df1'])
    mito.add_column(0, 'B')
    mito.code_options_update({'as_function': True, 'function_name': 'function', 'function_params': {}})

    print(mito.transpiled_code)
    assert mito.transpiled_code == [
        'from mitosheet.public.v3 import *',
        '',
        'def function(df1):',
        f"{TAB}df1.insert(1, 'B', 0)",
        f'{TAB}',
        f"{TAB}return df1",
        "",
        "df1 = function(df1)"
    ]

def test_transpile_as_function_string_params():
    tmp_file = 'txt.csv'
    df1 = pd.DataFrame({'A': [1], 'B': [2]})
    df1.to_csv(tmp_file, index=False)

    mito = create_mito_wrapper(str(tmp_file), arg_names=[f"'{tmp_file}'"])
    mito.code_options_update({'as_function': True, 'function_name': 'function', 'function_params': {}})

    assert mito.transpiled_code == [
        'from mitosheet.public.v3 import *',
        'import pandas as pd',
        '',
        'def function(txt_path):',
        f"{TAB}# Read in filepaths as dataframes",
        f"{TAB}txt = pd.read_csv(txt_path)",
        f'{TAB}',
        f"{TAB}return txt",
        "",
        "txt = function('txt.csv')"
    ]

    os.remove(tmp_file)

def test_transpile_as_function_string_params_no_args_update():
    tmp_file = 'txt.csv'
    df1 = pd.DataFrame({'A': [1], 'B': [2]})
    df1.to_csv(tmp_file, index=False)

    mito = create_mito_wrapper(str(tmp_file))
    mito.code_options_update({'as_function': True, 'function_name': 'function', 'function_params': {}})

    assert mito.transpiled_code == [
        'from mitosheet.public.v3 import *',
        'import pandas as pd',
        '',
        'def function(txt_path):',
        f"{TAB}# Read in filepaths as dataframes",
        f"{TAB}txt = pd.read_csv(txt_path)",
        f'{TAB}',
        f"{TAB}return txt",
        "",
        'txt = function("txt.csv")'
    ]

    os.remove(tmp_file)

def test_transpile_as_function_both_params():
    tmp_file = 'txt.csv'
    df1 = pd.DataFrame({'A': [1], 'B': [2]})
    df1.to_csv(tmp_file, index=False)

    mito = create_mito_wrapper(df1, str(tmp_file), arg_names=['df1', f"'{tmp_file}'"])
    mito.code_options_update({'as_function': True, 'function_name': 'function', 'function_params': {}})

    assert mito.transpiled_code == [
        'from mitosheet.public.v3 import *',
        'import pandas as pd',
        '',
        'def function(df1, txt_path):',
        f"{TAB}# Read in filepaths as dataframes",
        f"{TAB}txt = pd.read_csv(txt_path)",
        f'{TAB}',
        f"{TAB}return df1, txt",
        "",
        "df1, txt = function(df1, 'txt.csv')"
    ]

    os.remove(tmp_file)


def test_transpile_pivot_table_indents():
    df1 = pd.DataFrame(data={'Name': ['Nate', 'Nate'], 'Height': [4, 5]})
    mito = create_mito_wrapper(df1, arg_names=['df1'])

    mito.code_options_update({'as_function': True, 'function_name': 'function', 'function_params': {}})

    mito.pivot_sheet(
        0, 
        ['Name'],
        [],
        {'Height': ['sum']}
    )
    
    print("\n".join(mito.transpiled_code))
    assert "    pivot_table = tmp_df.pivot_table(\n        index=['Name'],\n        values=['Height'],\n        aggfunc={'Height': ['sum']}\n    )" in mito.transpiled_code


def test_transpile_as_function_single_param(tmp_path):
    tmp_file = str(tmp_path / 'txt.csv')
    df1 = pd.DataFrame({'A': [1], 'B': [2]})
    df1.to_csv(tmp_file, index=False)

    mito = create_mito_wrapper()
    mito.simple_import([tmp_file])
    mito.code_options_update({'as_function': True, 'function_name': 'function', 'function_params': {'var_name': f"r'{tmp_file}'"}})

    assert mito.transpiled_code == [
        'from mitosheet.public.v3 import *',
        "import pandas as pd",
        "",
        "def function(var_name):",
        f"{TAB}txt = pd.read_csv(var_name)",
        f'{TAB}',
        f"{TAB}return txt",
        "",
        f"var_name = r'{tmp_file}'",
        "",
        f"txt = function(var_name)"
    ]


def test_transpile_as_function_both_params_and_additional():
    tmp_file = 'txt.csv'
    df1 = pd.DataFrame({'A': [1], 'B': [2]})
    df1.to_csv(tmp_file, index=False)

    mito = create_mito_wrapper(df1, str(tmp_file), arg_names=['df1', f"'{tmp_file}'"])
    mito.simple_import([tmp_file])
    mito.code_options_update({'as_function': True, 'function_name': 'function', 'function_params': {'var_name': f"r'{tmp_file}'"}})

    assert mito.transpiled_code == [
        'from mitosheet.public.v3 import *',
        'import pandas as pd',
        '',
        'def function(df1, txt_path, var_name):',
        f"{TAB}# Read in filepaths as dataframes",
        f"{TAB}txt = pd.read_csv(txt_path)",
        f'{TAB}',
        '    txt_1 = pd.read_csv(var_name)',
        f'{TAB}',
        f"{TAB}return df1, txt, txt_1",
        "",
        f"var_name = r'{tmp_file}'",
        "",
        f"df1, txt, txt_1 = function(df1, 'txt.csv', var_name)"
    ]

    os.remove(tmp_file)

def test_transpile_as_function_single_param_multiple_times(tmp_path):
    tmp_file = str(tmp_path / 'txt.csv')
    df1 = pd.DataFrame({'A': [1], 'B': [2]})
    df1.to_csv(tmp_file, index=False)

    mito = create_mito_wrapper()
    mito.simple_import([tmp_file])
    mito.simple_import([tmp_file])
    mito.code_options_update({'as_function': True, 'function_name': 'function', 'function_params': {'var_name': f"r'{tmp_file}'"}})

    assert mito.transpiled_code == [
        'from mitosheet.public.v3 import *',
        "import pandas as pd",
        "",
        "def function(var_name):",
        f"{TAB}txt = pd.read_csv(var_name)",
        f"{TAB}txt_1 = pd.read_csv(var_name)",
        f'{TAB}',
        f"{TAB}return txt, txt_1",
        "",
        f"var_name = r'{tmp_file}'",
        "",
        f"txt, txt_1 = function(var_name)"
    ]

def test_transpile_as_function_multiple_params(tmp_path):
    tmp_file1 = str(tmp_path / 'txt.csv')
    tmp_file2 = str(tmp_path / 'file.csv')
    df1 = pd.DataFrame({'A': [1], 'B': [2]})
    df1.to_csv(tmp_file1, index=False)
    df1.to_csv(tmp_file2, index=False)

    mito = create_mito_wrapper()
    mito.simple_import([tmp_file1])
    mito.simple_import([tmp_file2])
    mito.code_options_update({'as_function': True, 'function_name': 'function', 'function_params': {'var_name1': f"r'{tmp_file1}'", 'var_name2': f"r'{tmp_file2}'"}})

    assert mito.transpiled_code == [
        'from mitosheet.public.v3 import *',
        "import pandas as pd",
        "",
        "def function(var_name1, var_name2):",
        f"{TAB}txt = pd.read_csv(var_name1)",
        f"{TAB}file = pd.read_csv(var_name2)",
        f'{TAB}',
        f"{TAB}return txt, file",
        "",
        f"var_name1 = r'{tmp_file1}'",
        f"var_name2 = r'{tmp_file2}'",
        "",
        f"txt, file = function(var_name1, var_name2)"
    ]

@pandas_post_1_2_only
@python_post_3_6_only
def test_transpile_parameterize_excel_imports(tmp_path):
    tmp_file = str(tmp_path / 'txt.xlsx')
    df1 = pd.DataFrame({'A': [1], 'B': [2]})
    df1.to_excel(tmp_file, index=False)

    mito = create_mito_wrapper()
    mito.excel_import(tmp_file, sheet_names=['Sheet1'], has_headers=True, skiprows=0)
    mito.excel_range_import(tmp_file, {'type': 'sheet name', 'value': 'Sheet1'}, [{'type': 'range', 'df_name': 'dataframe_1', 'value': 'A1:B2'}], convert_csv_to_xlsx=False)
    mito.code_options_update({'as_function': True, 'function_name': 'function', 'function_params': {'var_name': f"r'{tmp_file}'"}})

    assert mito.transpiled_code == [
        'from mitosheet.public.v3 import *',
        "import pandas as pd",
        "",
        "def function(var_name):",
        f"{TAB}sheet_df_dictonary = pd.read_excel(var_name, engine='openpyxl', sheet_name=['Sheet1'], skiprows=0)",
        f"{TAB}Sheet1 = sheet_df_dictonary['Sheet1']",
        f'{TAB}',
        f"{TAB}dataframe_1 = pd.read_excel(var_name, sheet_name='Sheet1', skiprows=0, nrows=1, usecols='A:B')",
        f'{TAB}',
        f"{TAB}return Sheet1, dataframe_1",
        "",
        f"var_name = r'{tmp_file}'",
        "",
        f"Sheet1, dataframe_1 = function(var_name)"
    ]

def test_transpile_with_function_params_over_mitosheet():
    df1 = pd.DataFrame({'A': [1], 'B': [2]})
    df2 = pd.DataFrame({'A': [1], 'B': [2]})
    mito = create_mito_wrapper(df1, df2, arg_names=['df', 'df_copy'])
    mito.add_column(0, 'C')
    mito.add_column(1, 'C')

    mito.code_options_update({'as_function': True, 'function_name': 'function', 'function_params': {'param': "df"}})

    
    assert mito.transpiled_code == [
        'from mitosheet.public.v3 import *',
        "",
        "def function(param, df_copy):",
        f"{TAB}param.insert(2, 'C', 0)",
        f"{TAB}",
        f"{TAB}df_copy.insert(2, 'C', 0)",
        f"{TAB}",
        f"{TAB}return param, df_copy",
        "",
        f"param = df",
        "",
        f"param, df_copy = function(param, df_copy)"
    ]

def test_transpile_does_not_effect_chars_in_strings():
    mito = create_mito_wrapper()
    quote = '"'
    mito.ai_transformation(
        'do a test',
        'v1',
        'test',
        'test',
        """
df = pd.DataFrame({'A': ["has a new \
line in it", '\t', '     ']})
        """
    )

    mito.code_options_update({'as_function': True, 'function_name': 'function', 'function_params': {}})

    assert "\n".join(mito.transpiled_code) == """from mitosheet.public.v3 import *
import pandas as pd

def function():
    df = pd.DataFrame({'A': ["has a new \
line in it", '\t', '     ']})
    
    return df

df = function()"""

def test_transpile_with_multiline_ai_completion():
    mito = create_mito_wrapper()
    mito.ai_transformation(
        'do a test',
        'v1',
        'test',
        'test',
        """
import pandas as pd

# create sample dataframe
df = pd.DataFrame({'A': [1, 2, 3], 'B': [4, 5, 6], 'C': [7, 8, 9]})

print(df)
        """
    )

    mito.code_options_update({'as_function': True, 'function_name': 'function', 'function_params': {}})

    assert "\n".join(mito.transpiled_code) == """from mitosheet.public.v3 import *

def function():
    import pandas as pd
    
    # create sample dataframe
    df = pd.DataFrame({'A': [1, 2, 3], 'B': [4, 5, 6], 'C': [7, 8, 9]})
    
    print(df)
    
    return df

df = function()"""

def test_transpiled_with_export_to_csv_singular():
    df = pd.DataFrame({'A': [1, 2, 3]})
    mito = create_mito_wrapper(df, arg_names=['df'])
    mito.export_to_file('csv', [0], 'te"st.csv')

    assert [('df', 'df_name', 'Dataframe'), ("r'te" + '"' + "st.csv'", 'file_name', 'CSV export file path')] == get_parameterizable_params({}, mito.mito_backend.steps_manager)

    mito.code_options_update({'as_function': True, 'function_name': 'function', 'function_params': {'path': "r'te" + '"' + "st.csv'"}})

    assert "\n".join(mito.transpiled_code) == """from mitosheet.public.v3 import *

def function(df, path):
    df.to_csv(path, index=False)
    
    return df

path = r'te"st.csv'

df = function(df, path)"""

def test_transpiled_with_export_to_csv_multiple():
    df = pd.DataFrame({'A': [1, 2, 3]})
    mito = create_mito_wrapper(df, df, arg_names=['df1', 'df2'])
    mito.export_to_file('csv', [0, 1], 'test.csv')

    assert [('df1', 'df_name', 'Dataframe'), ('df2', 'df_name', 'Dataframe'), ("r'test_0.csv'", 'file_name', 'CSV export file path'), ("r'test_1.csv'", 'file_name', 'CSV export file path')] == get_parameterizable_params({}, mito.mito_backend.steps_manager)

    mito.code_options_update({'as_function': True, 'function_name': 'function', 'function_params': {'path_0': "r'test_0.csv'", 'path_1': "r'test_1.csv'"}})

    assert "\n".join(mito.transpiled_code) == """from mitosheet.public.v3 import *

def function(df1, df2, path_0, path_1):
    df1.to_csv(path_0, index=False)
    df2.to_csv(path_1, index=False)
    
    return df1, df2

path_0 = r'test_0.csv'
path_1 = r'test_1.csv'

df1, df2 = function(df1, df2, path_0, path_1)"""

def test_transpiled_with_export_to_xlsx_single():
    df = pd.DataFrame({'A': [1, 2, 3]})
    mito = create_mito_wrapper(df, arg_names=['df'])
    mito.export_to_file('excel', [0], "te'st.xlsx")

    assert [('df', 'df_name', 'Dataframe'), ('r"te' + "'" + 'st.xlsx"', 'file_name', 'Excel export file path')] == get_parameterizable_params({}, mito.mito_backend.steps_manager)

    mito.code_options_update({'as_function': True, 'function_name': 'function', 'function_params': {'path': 'r"te' + "'" + 'st.xlsx"'}})

    assert "\n".join(mito.transpiled_code) == """from mitosheet.public.v3 import *
import pandas as pd

def function(df, path):
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="df", index=False)
    
    return df

path = r"te'st.xlsx"

df = function(df, path)"""

def test_transpiled_with_export_to_xlsx_multiple():
    df = pd.DataFrame({'A': [1, 2, 3]})
    mito = create_mito_wrapper(df, df, arg_names=['df1', 'df2'])
    mito.export_to_file('excel', [0, 1], 'test.xlsx')

    assert [('df1', 'df_name', 'Dataframe'), ('df2', 'df_name', 'Dataframe'), ("r'test.xlsx'", 'file_name', 'Excel export file path')] == get_parameterizable_params({}, mito.mito_backend.steps_manager)

    mito.code_options_update({'as_function': True, 'function_name': 'function', 'function_params': {'path_0': "r'test.xlsx'"}})

    assert "\n".join(mito.transpiled_code) == """from mitosheet.public.v3 import *
import pandas as pd

def function(df1, df2, path_0):
    with pd.ExcelWriter(path_0, engine="openpyxl") as writer:
        df1.to_excel(writer, sheet_name="df1", index=False)
        df2.to_excel(writer, sheet_name="df2", index=False)
    
    return df1, df2

path_0 = r'test.xlsx'

df1, df2 = function(df1, df2, path_0)"""

