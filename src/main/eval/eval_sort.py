import pandas as pd

acc_dict = { 1:0, 3:0, 5:0, 10:0 }
# total_samples = 350
total_samples = 500

def rank_acc(df):
    global acc_dict
    global total_samples

    acc_dict = { 1:0, 3:0, 5:0, 10:0 }

    def acc_at_ten(df_slice):
        global acc_dict
        global total_samples

        # total_samples += 1
        for (idx, (_, row)) in enumerate(df_slice.iterrows()):
            if row['Correct'] == 1 or row['Correct'] == '1':
                for key in acc_dict.keys():
                    if key >= idx:
                        acc_dict[key] = acc_dict[key] + 1
                break

    df.groupby('ClassName#TestName').apply(acc_at_ten)
    acc_dict = { key:acc_dict[key]/total_samples for key in acc_dict.keys() }

    return acc_dict


teco = pd.read_csv('../../res/teco-res.tsv', sep='\t')
# lmany = pd.read_csv('../../data/venn/lmany.tsv', sep='\t')
lmany = pd.read_csv('../../res/chatgpt.tsv', sep='\t')
lmany_fuzz = pd.read_csv('../../data/venn/lmany-fuzz.tsv', sep='\t')
# tatu = pd.read_csv('../../data/venn/chatassert-res.tsv', sep='\t')
tatu = pd.read_csv('../../res/chatassert-res500.tsv', sep='\t')
minus_ex = pd.read_csv('../../res/minus-ex500.tsv', sep='\t')
minus_sr = pd.read_csv('../../res/minus-sr500.tsv', sep='\t')
minus_cs = pd.read_csv('../../res/minus-cs500.tsv', sep='\t')
minus_dr = pd.read_csv('../../res/minus-dr500.tsv', sep='\t')

# teco['ClassName#TestName'] = teco['ClassName'] + '#' + tatu['TestName']
tatu['ClassName#TestName'] = tatu['ClassName'] + '#' + tatu['TestName']
lmany['ClassName#TestName'] = lmany['ClassName'] + '#' + lmany['TestName']
lmany_fuzz['ClassName#TestName'] = lmany_fuzz['ClassName'] + '#' + lmany_fuzz['TestName']
minus_ex['ClassName#TestName'] = minus_ex['ClassName'] + '#' + minus_ex['TestName']
minus_sr['ClassName#TestName'] = minus_sr['ClassName'] + '#' + minus_sr['TestName']
minus_cs['ClassName#TestName'] = minus_cs['ClassName'] + '#' + minus_cs['TestName']
minus_dr['ClassName#TestName'] = minus_dr['ClassName'] + '#' + minus_dr['TestName']

print('TECO')
print(rank_acc(teco))
print('TATU')
print(rank_acc(tatu))
print('LMANY')
print(rank_acc(lmany))
print('LMANY-FUZZ')
print(rank_acc(lmany_fuzz))
print('MINUS-EX')
print(rank_acc(minus_ex))
print('MINUS-SR')
print(rank_acc(minus_sr))
print('MINUS-CS')
print(rank_acc(minus_cs))
print('MINUS-DR')
print(rank_acc(minus_dr))
