import pandas as pd
from scipy import stats
from scipy.stats import chi2_contingency
import matplotlib.pyplot as plt

file_path_lmany = '../../res/chatgpt.tsv'
# file_path_lmany_fuzz = '../../../artifacts/lmany-fuzz.tsv'
file_path_chatassert = '../../res/chatassert-res500.tsv'
file_path_teco = '../../res/teco-res.tsv'

data_lmany = pd.read_csv(file_path_lmany, sep='\t')
# data_lmany_fuzz = pd.read_csv(file_path_lmany_fuzz, sep='\t')
data_chatassert = pd.read_csv(file_path_chatassert, sep='\t')
data_teco = pd.read_csv(file_path_teco, sep='\t')

data_lmany['ClassName#TestName'] = data_lmany['ClassName'] + '#' + data_lmany['TestName']
data_chatassert['ClassName#TestName'] = data_chatassert['ClassName'] + '#' + data_chatassert['TestName']

def preprocess_data(data):
    preprocessed_data = data.groupby(['ClassName#TestName'], as_index=False)['Correct'].max()
    return preprocessed_data

data_lmany_preprocessed = preprocess_data(data_lmany)
# data_lmany_fuzz_preprocessed = preprocess_data(data_lmany_fuzz)
data_chatassert_preprocessed = preprocess_data(data_chatassert)
data_teco_preprocessed = preprocess_data(data_teco)

def ensure_all_combinations(teco_data, other_data):
    teco_classes_tests = teco_data[['ClassName#TestName']]
    merged_data = teco_classes_tests.merge(other_data, on=['ClassName#TestName'], how='left').fillna({'Correct': 0})
    return merged_data

data_lmany_preprocessed = ensure_all_combinations(data_teco_preprocessed, data_lmany_preprocessed)
# data_lmany_fuzz_preprocessed = ensure_all_combinations(data_teco_preprocessed, data_lmany_fuzz_preprocessed)
data_chatassert_preprocessed = ensure_all_combinations(data_teco_preprocessed, data_chatassert_preprocessed)

correct_counts_lmany = data_lmany_preprocessed['Correct'].value_counts().sort_index()
# correct_counts_lmany_fuzz = data_lmany_fuzz_preprocessed['Correct'].value_counts().sort_index()
correct_counts_chatassert = data_chatassert_preprocessed['Correct'].value_counts().sort_index()
correct_counts_teco = data_teco_preprocessed['Correct'].value_counts().sort_index()

# Create contingency tables for pairwise comparisons later
contingency_lmany_chatassert = pd.DataFrame({
    'lmany': correct_counts_lmany,
    'chatassert': correct_counts_chatassert
}).fillna(0).astype(int)

# contingency_lmany_teco = pd.DataFrame({
#     'lmany': correct_counts_lmany,
#     'teco': correct_counts_teco
# }).fillna(0).astype(int)

contingency_chatassert_teco = pd.DataFrame({
    'chatassert': correct_counts_chatassert,
    'teco': correct_counts_teco
}).fillna(0).astype(int)

# contingency_lmany_lmany_fuzz = pd.DataFrame({
#     'lmany': correct_counts_lmany,
#     'lmany_fuzz': correct_counts_lmany_fuzz
# }).fillna(0).astype(int)

# contingency_lmany_fuzz_chatassert = pd.DataFrame({
#     'lmany_fuzz': correct_counts_lmany_fuzz,
#     'chatassert': correct_counts_chatassert
# }).fillna(0).astype(int)

# contingency_lmany_fuzz_teco = pd.DataFrame({
#     'lmany_fuzz': correct_counts_lmany_fuzz,
#     'teco': correct_counts_teco
# }).fillna(0).astype(int)

# Perform pairwise Chi-Square tests
chi2_lmany_chatassert, p_chi2_lmany_chatassert, _, _ = chi2_contingency(contingency_lmany_chatassert)
# chi2_lmany_teco, p_chi2_lmany_teco, _, _ = chi2_contingency(contingency_lmany_teco)
chi2_chatassert_teco, p_chi2_chatassert_teco, _, _ = chi2_contingency(contingency_chatassert_teco)
# chi2_lmany_lmany_fuzz, p_chi2_lmany_lmany_fuzz, _, _ = chi2_contingency(contingency_lmany_lmany_fuzz)
# chi2_lmany_fuzz_chatassert, p_chi2_lmany_fuzz_chatassert, _, _ = chi2_contingency(contingency_lmany_fuzz_chatassert)
# chi2_lmany_fuzz_teco, p_chi2_lmany_fuzz_teco, _, _ = chi2_contingency(contingency_lmany_fuzz_teco)

print(f'Chi-Square Test for Independence - lmany vs chatassert\nChi2: {chi2_lmany_chatassert}\nP-value: {p_chi2_lmany_chatassert}\n')
# print(f'Chi-Square Test for Independence - lmany vs teco\nChi2: {chi2_lmany_teco}\nP-value: {p_chi2_lmany_teco}\n')
print(f'Chi-Square Test for Independence - chatassert vs teco\nChi2: {chi2_chatassert_teco}\nP-value: {p_chi2_chatassert_teco}\n')
# print(f'Chi-Square Test for Independence - lmany vs lmany_fuzz\nChi2: {chi2_lmany_lmany_fuzz}\nP-value: {p_chi2_lmany_lmany_fuzz}\n')
# print(f'Chi-Square Test for Independence - lmany_fuzz vs chatassert\nChi2: {chi2_lmany_fuzz_chatassert}\nP-value: {p_chi2_lmany_fuzz_chatassert}\n')
# print(f'Chi-Square Test for Independence - lmany_fuzz vs teco\nChi2: {chi2_lmany_fuzz_teco}\nP-value: {p_chi2_lmany_fuzz_teco}\n')

# Calculate proportions for effect size
prop_lmany = correct_counts_lmany[1] / correct_counts_lmany.sum()
# prop_lmany_fuzz = correct_counts_lmany_fuzz[1] / correct_counts_lmany_fuzz.sum()
prop_chatassert = correct_counts_chatassert[1] / correct_counts_chatassert.sum()
prop_teco = correct_counts_teco[1] / correct_counts_teco.sum()

# Cohen's h effect size for proportions
def cohens_h(p1, p2):
    return 2 * (stats.norm.ppf(p1) - stats.norm.ppf(p2))

effect_size1 = cohens_h(prop_lmany, prop_chatassert)
# effect_size2 = cohens_h(prop_lmany, prop_teco)
effect_size3 = cohens_h(prop_chatassert, prop_teco)
# effect_size4 = cohens_h(prop_lmany, prop_lmany_fuzz)
# effect_size5 = cohens_h(prop_lmany_fuzz, prop_chatassert)
# effect_size6 = cohens_h(prop_lmany_fuzz, prop_teco)

print(f'Effect Size (Cohen\'s h):')
print(f'lmany vs chatassert: {effect_size1}\n')
# print(f'lmany vs teco: {effect_size2}\n')
print(f'chatassert vs teco: {effect_size3}\n')
# print(f'lmany vs lmany_fuzz: {effect_size4}\n')
# print(f'lmany_fuzz vs chatassert: {effect_size5}\n')
# print(f'lmany_fuzz vs teco: {effect_size6}\n')

# Normality Test on proportions
normality_lmany = stats.shapiro(data_lmany['Correct'])
# normality_lmany_fuzz = stats.shapiro(data_lmany_fuzz['Correct'])
normality_chatassert = stats.shapiro(data_chatassert['Correct'])
normality_teco = stats.shapiro(data_teco['Correct'])
print('Normality Test Results:')
print(f'lmany: {normality_lmany}')
# print(f'lmany_fuzz: {normality_lmany_fuzz}')
print(f'chatassert: {normality_chatassert}')
print(f'teco: {normality_teco}')

# Plot
contingency_table = pd.DataFrame({
    'lmany': correct_counts_lmany,
    # 'lmany_fuzz': correct_counts_lmany_fuzz,
    'chatassert': correct_counts_chatassert,
    'teco': correct_counts_teco
}).fillna(0).astype(int)

contingency_table_prop = contingency_table.div(contingency_table.sum(axis=0), axis=1)
contingency_table_prop.plot(kind='bar', stacked=True)

plt.title('Proportion of Correct Assertions Across Groups')
plt.xlabel('Correct')
plt.ylabel('Proportion')
plt.xticks(rotation=0)
plt.legend(title='Dataset')
plt.savefig('proportion_correct_assertions.png', bbox_inches='tight', dpi=300)

def print_summary(dataset_name, normality_result, p_value, effect_size, effect_size_class):
    is_normal = "not normal" if normality_result.pvalue < 0.05 else "normal"
    is_significant = "statistically significant" if p_value < 0.05 else "not statistically significant"
    print(f'{dataset_name} data is {is_normal}')
    print(f'The difference is {is_significant}')
    print(f'The effect size is {effect_size} ({effect_size_class})\n')

def classify_effect_size(h):
    if abs(h) < 0.2:
        return 'negligible'
    elif abs(h) < 0.5:
        return 'small'
    elif abs(h) < 0.8:
        return 'medium'
    else:
        return 'large'

effect_size_class1 = classify_effect_size(effect_size1)
# effect_size_class2 = classify_effect_size(effect_size2)
effect_size_class3 = classify_effect_size(effect_size3)
# effect_size_class4 = classify_effect_size(effect_size4)
# effect_size_class5 = classify_effect_size(effect_size5)
# effect_size_class6 = classify_effect_size(effect_size6)

print('Summary for lmany vs chatassert:')
print_summary('lmany vs chatassert', normality_lmany, p_chi2_lmany_chatassert, effect_size1, effect_size_class1)

# print('Summary for lmany vs teco:')
# print_summary('lmany vs teco', normality_lmany, p_chi2_lmany_teco, effect_size2, effect_size_class2)

print('Summary for chatassert vs teco:')
print_summary('chatassert vs teco', normality_chatassert, p_chi2_chatassert_teco, effect_size3, effect_size_class3)

# print('Summary for lmany vs lmany_fuzz:')
# print_summary('lmany vs lmany_fuzz', normality_lmany, p_chi2_lmany_lmany_fuzz, effect_size4, effect_size_class4)

# print('Summary for lmany_fuzz vs chatassert:')
# print_summary('lmany_fuzz vs chatassert', normality_lmany_fuzz, p_chi2_lmany_fuzz_chatassert, effect_size5, effect_size_class5)

# print('Summary for lmany_fuzz vs teco:')
# print_summary('lmany_fuzz vs teco', normality_lmany_fuzz, p_chi2_lmany_fuzz_teco, effect_size6, effect_size_class6)
