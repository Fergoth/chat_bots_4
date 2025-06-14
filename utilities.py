import os


def get_damerau_levenshtein_distance(s1, s2):
    d = {}
    lenstr1 = len(s1)
    lenstr2 = len(s2)
    for i in range(-1, lenstr1 + 1):
        d[(i, -1)] = i + 1
    for j in range(-1, lenstr2 + 1):
        d[(-1, j)] = j + 1

    for i in range(lenstr1):
        for j in range(lenstr2):
            if s1[i] == s2[j]:
                cost = 0
            else:
                cost = 1
            d[(i, j)] = min(
                d[(i - 1, j)] + 1,
                d[(i, j - 1)] + 1,
                d[(i - 1, j - 1)] + cost,
            )
            if i and j and s1[i] == s2[j - 1] and s1[i - 1] == s2[j]:
                d[(i, j)] = min(d[(i, j)], d[i - 2, j - 2] + 1)
    return d[lenstr1 - 1, lenstr2 - 1]


def load_questions(folder_name):
    quiz = {}
    script_dir = os.path.dirname(os.path.abspath(__file__))
    for filename in os.listdir(os.path.join(script_dir, folder_name)):
        with open(
            os.path.join(script_dir, folder_name, filename), encoding="KOI8-R"
        ) as f:
            for section in f.read().split("\n\n"):
                section = section.strip()
                if section.startswith("Вопрос"):
                    curr_question = section.split("\n", 1)[1]
                elif section.startswith("Ответ"):
                    curr_answer = section.split("\n", 1)[1]
                    quiz[curr_question] = curr_answer
    return quiz


def check_answer(user_answer, correct_answer):
    cut_index = correct_answer.find("(")
    if cut_index == -1:
        cut_index = correct_answer.find(".")
    if cut_index == -1:
        cut_index = len(correct_answer) + 1
    correct_answer = correct_answer[:cut_index]
    levenshtein_index = 3
    return (
        get_damerau_levenshtein_distance(user_answer, correct_answer)
        <= len(correct_answer) // levenshtein_index
    )
