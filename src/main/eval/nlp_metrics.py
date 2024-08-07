import sys
import pandas as pd
from nltk import edit_distance
from bleu import corpus_bleu, SmoothingFunction
import weighted_ngram_match
import syntax_match
import dataflow_match

from rouge import Rouge
from rouge_metric import PyRouge
sys.setrecursionlimit(12250000)

def spacify(line):
    testString = []
    specialsPair = [ ['=', '='], ['+', '+'], ['-', '-'], ['+', '='], ['-', '='], ['*', '='], 
                            ['/', '='], ['%', '='], ['!', '='], ['>', '='], ['<', '='], ['&', '&'], 
                            ['|', '|'], ['<', '<'], ['>', '>'], ['-', '>'] ]
    specials = ['(', ')', '{', '}', '[', ']', ',', '.', ';', '+', '-', '*', '/', '%', '=', '>', '<', '!', '&', '^', '\"', '\'']

    inQuotes = False
    for i in range(0, len(line)):
        isSpecial = False
        
        # Check start of string literal
        if not inQuotes and line[i] == '"': 
            inQuotes = True
        # Check end of string literal
        elif inQuotes and line[i] == '"':
            inQuotes = False

        if not inQuotes:
            # Checking for special character modifications (e.g. inclusion of spaces) if not in a string literal
            for c in range(0, len(specialsPair)):
                # Matching compound operators (e.g. ++, -- etc.)
                if i < len(line) -1:
                    if line[i] == specialsPair[c][0] and line[i+1] == specialsPair[c][1]:
                        isSpecial = True
                        if len(testString) > 0:
                            if testString[len(testString)-1] != ' ':
                                testString.append(' ')
                        else:
                            testString.append(' ')

                        testString.append(specialsPair[c][0])
                        testString.append(specialsPair[c][1])
                        if i+1 < len(line) and line[i+1] != ' ':
                            testString.append(' ')
                        i += 1
                    
            if not isSpecial:
                # If no special compound operator is found, check for single special operators
                for c in range(0, len(specials)):
                    if line[i] == specials[c]:
                        if (line[i] == '.' and i > 0 and i < len(line)-1 and line[i+1].isdigit()):
                            # Avoiding spacifying dots in floats
                            continue

                        isSpecial = True
                        if i > 0 and line[i-1] != ' ':
                            if len(testString) > 0:
                                if testString[len(testString)-1] != ' ':
                                    testString.append(' ')
                            else:
                                testString.append(' ')
                            
                        testString.append(specials[c])
                        if i+1 < len(line) and line[i+1] != ' ':
                            testString.append(' ')
                    
        if not isSpecial and line[i] == '\n':
            # Skipping newlines because the ATLAS dataset format has no newlines in a sample
            testString.append(' ')
        elif not isSpecial and line[i] == '\r':
            if len(testString) > 0 and testString[len(testString)-1] != ' ':
                testString.append(' ')
        elif not isSpecial:
            # Non-special character should be included in the dataset without any modifications
            testString.append(line[i])
        
    testStringOut = ''.join([val for val in testString])

    return testStringOut

def prepare_refs_hyps(data):
    references = []
    hypotheses = []

    def group(df_slice):
        refs = []
        for idx, row in df_slice.iterrows():
            refs.append(spacify(row['GenOracle'].replace('org.junit.Assert.', '').replace('org.junit.', '').replace('Assert.', '')))
        references.append(refs)
        hypotheses.append(spacify(df_slice.iloc[0]['TrueOracle'].replace('org.junit.Assert.', '').replace('org.junit.', '').replace('Assert.', '')))
        
    data.groupby(['ClassName#TestName']).apply(group)

    return references, hypotheses

def bleu(data):
    references, hypotheses = prepare_refs_hyps(data)

    return corpus_bleu(references, hypotheses, weights=[0.25, 0.25, 0.25, 0.25], smoothing_function=SmoothingFunction().method2)

def code_bleu(data):
    references, hypotheses = prepare_refs_hyps(data)

    alpha,beta,gamma,theta=0.25,0.25,0.25,0.25

    # calculate ngram match (BLEU)
    tokenized_hyps = [x.split() for x in hypotheses]
    tokenized_refs = [[x.split() for x in reference] for reference in references]

    ngram_match_score = corpus_bleu(tokenized_refs,tokenized_hyps)

    # calculate weighted ngram match
    lang = 'java'
    keywords = [x.strip() for x in open('keywords/'+lang+'.txt', 'r', encoding='utf-8').readlines()]
    def make_weights(reference_tokens, key_word_list):
        return {token:1 if token in key_word_list else 0.2 \
                for token in reference_tokens}
    tokenized_refs_with_weights = [[[reference_tokens, make_weights(reference_tokens, keywords)]\
                for reference_tokens in reference] for reference in tokenized_refs]

    weighted_ngram_match_score = weighted_ngram_match.corpus_bleu(tokenized_refs_with_weights,tokenized_hyps)

    # calculate syntax match
    syntax_match_score = syntax_match.corpus_syntax_match(references, hypotheses, lang)

    # calculate dataflow match
    dataflow_match_score = dataflow_match.corpus_dataflow_match(references, hypotheses, lang)

    # print('ngram match: {0}, weighted ngram match: {1}, syntax_match: {2}, dataflow_match: {3}'.\
    #                    format(ngram_match_score, weighted_ngram_match_score, syntax_match_score, dataflow_match_score))

    code_bleu_score = alpha*ngram_match_score\
                    + beta*weighted_ngram_match_score\
                    + gamma*syntax_match_score\
                    + theta*dataflow_match_score

    # print('CodeBLEU score: ', code_bleu_score)

    return code_bleu_score

def rouge(data):
    references, hypotheses = prepare_refs_hyps(data)
    all_refs_list = []

    for per_test_refs in references:
        all_refs_list.append(' '.join(per_test_refs))
    all_refs = ' '.join(all_refs_list)

    all_hyps = ' '.join(hypotheses)

    rouge = Rouge()
    scores = rouge.get_scores(all_hyps, all_refs, avg=True)

    # rouge = PyRouge(rouge_n=(1, 2, 4), rouge_l=True, rouge_w=True,
    #             rouge_w_weight=1.2, rouge_s=True, rouge_su=True, skip_gap=4)
    # scores = rouge.evaluate(hypotheses, references)
    # print(scores)

    # return None
    return scores["rouge-l"]['f'] * 100.0

def edit_sim(data):
    score = 0
    for true, pred in zip(data['TrueOracle'], data['GenOracle']):
        true = true.replace('org.junit.Assert.', '').replace('org.junit.', '').replace('Assert.', '').replace(' ', '')
        pred = pred.replace('org.junit.Assert.', '').replace('org.junit.', '').replace('Assert.', '').replace(' ', '')

        score += edit_distance(true, pred)/max(len(true), len(pred))

    return 1-score/len(data)

def main():
    # dataOGPT = pd.read_csv('../../prelim_res.csv', sep='\t', usecols=['TestClass', 'TestName', 'TrueOracle', 'GenOracle'])
    dataOGPT = pd.read_csv('../../res/chatassert-res500.tsv', sep='\t', usecols=['ClassName', 'TestName', 'TrueOracle', 'GenOracle'])
    # dataTeco = pd.read_csv('../../teco_eval/teco/output/preds_processed.csv', sep='\t', usecols=['ClassName#TestName', 'TrueOracle', 'GenOracle'])
    dataTeco = pd.read_csv('../../res/teco-res.tsv', sep='\t', usecols=['ClassName#TestName', 'TrueOracle', 'GenOracle'])
    # dataBatch = pd.read_csv('../../prelim_res_batch.csv', sep='\t', usecols=['TestClass', 'TestName', 'TrueOracle', 'GenOracle'])
    # dataBatch = pd.read_csv('../../res/chatgpt.tsv', sep='\t', usecols=['ClassName', 'TestName', 'TrueOracle', 'GenOracle'])
    # dataBatchFuzz = pd.read_csv('../../prelim_res_batch_fuzz.csv', sep='\t', usecols=['TestClass', 'TestName', 'TrueOracle', 'GenOracle'])

    minusCS = pd.read_csv('../../res/minus-cs500.tsv', sep='\t', usecols=['ClassName', 'TestName', 'TrueOracle', 'GenOracle'])
    minusEX = pd.read_csv('../../res/minus-ex500.tsv', sep='\t', usecols=['ClassName', 'TestName', 'TrueOracle', 'GenOracle'])
    minusSR = pd.read_csv('../../res/minus-sr500.tsv', sep='\t', usecols=['ClassName', 'TestName', 'TrueOracle', 'GenOracle'])
    minusDR = pd.read_csv('../../res/minus-dr500.tsv', sep='\t', usecols=['ClassName', 'TestName', 'TrueOracle', 'GenOracle'])

    dataOGPT['ClassName#TestName'] = dataOGPT['ClassName'] + '#' + dataOGPT['TestName']
    # dataBatch['ClassName#TestName'] = dataBatch['ClassName'] + '#' + dataBatch['TestName']
    # dataBatchFuzz['ClassName#TestName'] = dataBatchFuzz['TestClass'] + '#' + dataBatchFuzz['TestName']
    minusCS['ClassName#TestName'] = minusCS['ClassName'] + '#' + minusCS['TestName']
    minusEX['ClassName#TestName'] = minusEX['ClassName'] + '#' + minusEX['TestName']
    minusSR['ClassName#TestName'] = minusSR['ClassName'] + '#' + minusSR['TestName']
    minusDR['ClassName#TestName'] = minusDR['ClassName'] + '#' + minusDR['TestName']

    print('OGPT BLEU: {}'.format(bleu(dataOGPT)))
    print('Teco BLEU: {}'.format(bleu(dataTeco)))
    # print('Batch BLEU: {}'.format(bleu(dataBatch)))
    # print('Batch-Fuzz BLEU: {}'.format(bleu(dataBatchFuzz)))
    print('MinusCS BLEU: {}'.format(bleu(minusCS)))
    print('MinusEX BLEU: {}'.format(bleu(minusEX)))
    print('MinusSR BLEU: {}'.format(bleu(minusSR)))
    print('MinusDR BLEU: {}'.format(bleu(minusDR)))

    # print('OGPT CodeBLEU: {}'.format(code_bleu(dataOGPT)))
    # print('Teco CodeBLEU: {}'.format(code_bleu(dataTeco)))
    # print('Batch CodeBLEU: {}'.format(code_bleu(dataBatch)))
    # print('Batch-Fuzz CodeBLEU: {}'.format(code_bleu(dataBatchFuzz)))
    # print('MinusCS CodeBLEU: {}'.format(code_bleu(minusCS)))
    # print('MinusEX CodeBLEU: {}'.format(code_bleu(minusEX)))
    # print('MinusSR CodeBLEU: {}'.format(code_bleu(minusSR)))
    # print('MinusDR CodeBLEU: {}'.format(code_bleu(minusDR)))

    print('OGPT Rouge: {}'.format(rouge(dataOGPT)))
    print('Teco Rouge: {}'.format(rouge(dataTeco)))
    # print('Batch Rouge: {}'.format(rouge(dataBatch)))
    # print('Batch-Fuzz Rouge: {}'.format(rouge(dataBatchFuzz)))
    print('MinusCS Rouge: {}'.format(rouge(minusCS)))
    print('MinusEX Rouge: {}'.format(rouge(minusEX)))
    print('MinusSR Rouge: {}'.format(rouge(minusSR)))
    print('MinusDR Rouge: {}'.format(rouge(minusDR)))

    print('OGPT Edit Distance: {}'.format(edit_sim(dataOGPT)))
    print('Teco Edit Distance: {}'.format(edit_sim(dataTeco)))
    # print('Batch Edit Distance: {}'.format(edit_sim(dataBatch)))
    # print('Batch-Fuzz Edit Distance: {}'.format(edit_sim(dataBatchFuzz)))
    print('MinusCS Edit Distance: {}'.format(edit_sim(minusCS)))
    print('MinusEX Edit Distance: {}'.format(edit_sim(minusEX)))
    print('MinusSR Edit Distance: {}'.format(edit_sim(minusSR)))
    print('MinusDR Edit Distance: {}'.format(edit_sim(minusDR)))

main()
