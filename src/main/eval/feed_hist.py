import pandas as pd
pd.set_option('display.max_colwidth', None)
pd.set_option('display.max_columns', None)

hist_interaction_index_dict = {k:0 for k in range(1, 31)}
hist_assertion_kind_dict = {}
assertion_kind_idx = {}

common_assertion_kinds = ['assertEquals', 'assertNotEquals', 'assertSame', 'assertNotSame', 'assertTrue', 'assertFalse', 'assertNull', 'assertNotNull', 'assertArrayEquals', 'assertThat']

teco = pd.read_csv('../../data/venn/teco-res.tsv', sep='\t')
tatu = pd.read_csv('../../data/venn/oragen-res-with-feedback.tsv', sep='\t')
only_teco_df = pd.read_csv('../../data/venn/res/only-teco.tsv', sep='\t')
none_df = pd.read_csv('../../data/venn/res/none.tsv', sep='\t')

def hist_interaction_index():
    global hist_interaction_index_dict

    def tatu_fn(df_slice):
        global hist_interaction_index_dict
        testName = df_slice['TestName'].iloc[0]

        for (idx, row) in df_slice.iterrows():
            if row['Correct'] == 1:
                hist_interaction_index_dict[row['OracleID']+1] += 1
                break

    tatu['ClassName#TestName'] = tatu['ClassName'] + '#' + tatu['TestName']
    tatu.groupby('ClassName#TestName').apply(tatu_fn)
    for (k, v) in hist_interaction_index_dict.items():
        print(str(k) + ': ' + str(v))

def hist_assertion_kind(df):
    global hist_assertion_kind_dict
    global assertion_kind_idx

    def hist_fn(df_slice):
        global hist_assertion_kind_dict
        global assertion_kind_idx
        global weird_cnt

        assertionKind = df_slice.iloc[0]['TrueOracle'].split('(')[0].replace('org.junit.Assert.', '').replace('junit.Assert.', '').replace('Assert.', '')
        if assertionKind not in hist_assertion_kind_dict:
            hist_assertion_kind_dict[assertionKind] = 1
        else:
            hist_assertion_kind_dict[assertionKind] += 1

        if assertionKind not in assertion_kind_idx:
            assertion_kind_idx[assertionKind] = []

        for (idx, row) in df_slice.iterrows():
            assertion_kind_idx[assertionKind].append(idx)

    df.groupby('ClassName#TestName').apply(hist_fn)

    weird_cnt = 0
    for (k, v) in hist_assertion_kind_dict.items():
        print(str(k) + ': ' + str(v))
        if k not in common_assertion_kinds: weird_cnt += v

    # for (k, v) in assertion_kind_idx.items():
    #     print(str(k) + ': ', end='')
    #     print(v)

    print('\nHelper Assertions Count: {}\n'.format(weird_cnt))

hist_interaction_index()
# hist_assertion_kind(only_teco_df)