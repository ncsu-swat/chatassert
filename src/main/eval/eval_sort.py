import pandas as pd

acc_dict = { 1:0, 3:0, 5:0, 10:0 }
total_samples = 0

def rank_acc():
    global acc_dict
    global total_samples

    preds_processed = pd.read_csv('../../res_sorted_all.csv', sep='\t')

    def acc_at_ten(df_slice):
        global acc_dict
        global total_samples

        total_samples += 1
        for (idx, (_, row)) in enumerate(df_slice.iterrows()):
            if row['Correct'] == 1:
                for key in acc_dict.keys():
                    if key >= idx:
                        acc_dict[key] = acc_dict[key] + 1
                break

    preds_processed.groupby('TestID').apply(acc_at_ten)
    acc_dict = { key:acc_dict[key]/total_samples for key in acc_dict.keys() }

    return acc_dict

print(rank_acc())