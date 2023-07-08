import pandas as pd
pd.set_option('display.max_colwidth', None)
pd.set_option('display.max_columns', None)

import sys
sys.path.append('../utils')
from markdown_util import get_assert_type

TECO = 0
TATU = 1
BR = 2

common_assertion_kinds = ['assertEquals', 'assertNotEquals', 'assertSame', 'assertNotSame', 'assertTrue', 'assertFalse', 'assertNull', 'assertNotNull', 'assertArrayEquals']

teco_cnt, tatu_cnt, br_cnt = 0, 0, 0
teco_tatu_cnt, teco_br_cnt, tatu_br_cnt = 0, 0, 0
teco_tatu_br_cnt = 0
corr_dict = dict()

teco = pd.read_csv('../../data/venn/teco-res.tsv', sep='\t')
tatu = pd.read_csv('../../data/venn/oragen-res-with-feedback-fuzzrepair.tsv', sep='\t')
# br = pd.read_csv('../../data/venn/oragen-res-batch-sort.tsv', sep='\t')

def teco_fn(df_slice):
    global corr_dict
    classTestName = df_slice['ClassName#TestName'].iloc[0]
    assertType = get_assert_type(df_slice['TrueOracle'].iloc[0])

    if assertType in common_assertion_kinds:
        if classTestName not in corr_dict: 
            corr_dict[classTestName] = []
        else:
            print(classTestName)

        for (idx, row) in df_slice.iterrows():
            if row['Correct'] == 1:
                corr_dict[classTestName].append(TECO)
                break

def tatu_fn(df_slice):
    global corr_dict
    classTestName = df_slice['ClassName#TestName'].iloc[0]
    assertType = get_assert_type(df_slice['TrueOracle'].iloc[0])

    if assertType in common_assertion_kinds:
        for (idx, row) in df_slice.iterrows():
            if row['Correct'] == 1:
                corr_dict[classTestName].append(TATU)
                break

def br_fn(df_slice):
    global corr_dict
    classTestName = df_slice['ClassName#TestName'].iloc[0]
    assertType = get_assert_type(df_slice['TrueOracle'].iloc[0])

    if assertType in common_assertion_kinds:
        for (idx, row) in df_slice.iterrows():
            if row['Correct'] == 1:
                corr_dict[classTestName].append(BR)
                break

tatu['ClassName#TestName'] = tatu['ClassName'] + '#' + tatu['TestName']
# br['ClassName#TestName'] = br['ClassName'] + '#' + br['TestName']

teco.groupby('ClassName#TestName').apply(teco_fn)
tatu.groupby('ClassName#TestName').apply(tatu_fn)
# br.groupby('ClassName#TestName').apply(br_fn)

with open('../../data/venn/res/only-teco.tsv', 'w+') as onlyTeco, open('../../data/venn/res/none.tsv', 'w+') as none:
    onlyTeco.write('ClassName#TestName\tTrueOracle\n')
    none.write('ClassName#TestName\tTrueOracle\n')

    for (classTestName, corr_arr) in corr_dict.items():
        if TECO in corr_arr and TATU in corr_arr:
            teco_tatu_cnt += 1
            continue

        if TECO in corr_arr and TATU not in corr_arr:
            teco_cnt += 1
            onlyTeco.write('{}\t{}\n'.format(classTestName, teco[teco['ClassName#TestName']==classTestName].iloc[0]['TrueOracle']))
            continue

        if TATU in corr_arr and TECO not in corr_arr:
            tatu_cnt += 1
            continue

    # for (classTestName, corr_arr) in corr_dict.items():
    #     if TECO in corr_arr and TATU in corr_arr and BR in corr_arr:
    #         teco_tatu_br_cnt += 1
    #         continue
        
    #     if TECO in corr_arr and TATU in corr_arr and BR not in corr_arr:
    #         teco_tatu_cnt += 1
    #         continue
        
    #     if TECO in corr_arr and BR in corr_arr and TATU not in corr_arr:
    #         teco_br_cnt += 1
    #         continue

    #     if TATU in corr_arr and BR in corr_arr and TECO not in corr_arr:
    #         tatu_br_cnt += 1
    #         continue

    #     if TECO in corr_arr and TATU not in corr_arr and BR not in corr_arr:
    #         teco_cnt += 1
    #         onlyTeco.write('{}\t{}\n'.format(classTestName, teco[teco['ClassName#TestName']==classTestName].iloc[0]['TrueOracle']))
    #         continue

    #     if TATU in corr_arr and TECO not in corr_arr and BR not in corr_arr:
    #         tatu_cnt += 1
    #         continue

    #     if BR in corr_arr and TECO not in corr_arr and TATU not in corr_arr:
    #         br_cnt += 1
    #         continue

    #     none.write('{}\t{}\n'.format(classTestName, teco[teco['ClassName#TestName']==classTestName].iloc[0]['TrueOracle']))

print('Total Samples: {}\n'.format(str(len(corr_dict))))
# print('teco-tatu-br: {}%\n\nteco-tatu: {}%\nteco-br: {}%\ntatu-br: {}%\n\nteco: {}%\ntatu: {}%\nbr: {}%'.format(teco_tatu_br_cnt/len(corr_dict), teco_tatu_cnt/len(corr_dict), teco_br_cnt/len(corr_dict), tatu_br_cnt/len(corr_dict), teco_cnt/len(corr_dict), tatu_cnt/len(corr_dict), br_cnt/len(corr_dict)))
print('teco-tatu: {}%\n\nteco: {}%\ntatu: {}%'.format(teco_tatu_cnt/len(corr_dict), teco_cnt/len(corr_dict), tatu_cnt/len(corr_dict)))

only_teco_df = pd.read_csv('../../data/venn/res/only-teco.tsv', sep='\t')
none_df = pd.read_csv('../../data/venn/res/none.tsv', sep='\t')
