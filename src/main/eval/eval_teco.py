import sys
import csv
import json
import pandas as pd

sys.path.append('../utils')
from markdown_util import clean_args, check_commutative_equal

global corr_count

teco_raw_preds_path = '../../teco_eval/teco/output/all_preds.jsonl'

def writeTecoPreds():
    with open('../../teco_eval/teco/input/id.jsonl', 'r') as ids_file,\
         open('../../teco_eval/teco/input/gold_stmts.jsonl', 'r') as golds_file,\
         open(teco_raw_preds_path, 'r') as preds_file,\
         open('../../teco_eval/teco/input/proj_name.jsonl', 'r') as proj_file,\
         open('../../teco_eval/teco/input/test_mkey.jsonl', 'r') as test_file,\
         open('../../teco_eval/teco/output/preds_processed.csv', 'w+') as preds_csv:
        
        ids = [json.loads(line) for line in ids_file]
        ids2lines = {id:i for (i, id) in enumerate(ids)}

        proj = [json.loads(line) for line in proj_file]
        tests = [json.loads(line) for line in test_file]
        golds = [json.loads(line) for line in golds_file]
        preds = [json.loads(line) for line in preds_file]

        csvWriter = csv.writer(preds_csv, delimiter='\t')
        csvWriter.writerow(['TestID', 'OracleID', 'Project', 'ClassName#TestName', 'TrueOracle', 'GenOracle', 'Correct'])
        for (i, pred) in enumerate(preds):
            for topPred in pred['topk']:
                # print(str(i), ''.join(gold).replace('Assert.', ''), ''.join(topPred['toks']).replace('Assert.', ''))
                goldAssert = clean_args(' '.join(golds[ids2lines[pred['data_id']]]))
                # goldAssert = ' '.join(golds[ids2lines[pred['data_id']]])
                goldAssert = goldAssert.replace('org.junit.Assert.', '')
                goldAssert = goldAssert.replace('Assert.', '')
                goldAssert = goldAssert.replace(' ', '')

                predAssert = check_commutative_equal(clean_args(' '.join(topPred['toks'])), goldAssert)
                # predAssert = ' '.join(topPred['toks'])
                predAssert = predAssert.replace('org.junit.Assert.', '')
                predAssert = predAssert.replace('Assert.', '')
                predAssert = predAssert.replace(' ', '')
                
                print('Gold: ' + goldAssert)
                print('Pred: ' + predAssert)

                isCorrect = 1 if goldAssert.strip()==predAssert.strip() else 0
                csvWriter.writerow("{}\t{}\t{}\t{}\t{}\t{}\t{}".format(str(i), str(len(pred['topk'])), proj[ids2lines[pred["data_id"]]], tests[ids2lines[pred["data_id"]]].split('/')[-1].split('(')[0], goldAssert, predAssert, str(isCorrect)).split('\t'))

def eval():
    global corr_count

    corr_count = 0
    preds_processed = pd.read_csv('../../teco_eval/teco/output/preds_processed.csv', sep='\t')
    
    if 'all' in teco_raw_preds_path: total_samples = 3540
    else: total_samples = 350

    def acc_at_ten(df_slice):
        for (idx, row) in df_slice.iterrows():
            global corr_count
            if row['Correct'] == 1:
                corr_count += 1
                break
            # break    # For Acc@1, we look at just the first instance

    preds_processed.groupby('TestID').apply(acc_at_ten)
    
    print(str(corr_count))
    print('Teco acc@10: {}%'.format(str(corr_count/total_samples)))

writeTecoPreds()
eval()

#------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

# # Ad-hoc script to check ogpt v1 accuracy on all Teco dataset
# corr_count = 0
# df = pd.read_csv('../../tmp_res_all.csv', sep='\t', usecols=['TrueOracle', 'GenOracle'])
# for (idx, row) in df.iterrows():
#     if row['TrueOracle'].strip().replace('org.junit.Assert.', '').replace('Assert.', '').replace(' ', '') == clean_args(check_commutative_equal(abstract_string_literals(row['GenOracle']), row['TrueOracle']).strip()).replace('org.junit.Assert.', '').replace('Assert.', '').replace(' ', ''):
#         corr_count += 1
# print(corr_count)