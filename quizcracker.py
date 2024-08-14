import openai
import json

# Set your OpenAI API key
openai.api_key = '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'  # Replace with your OpenAI API key

def generate_interview_questions(topic, difficulty, max_questions, question_type):
    questions = []

    for _ in range(max_questions):
        if question_type == 'mcq':
            prompt = (
                f"Generate a realistic multiple-choice interview question for a {difficulty} level "
                f"related to {topic}. Provide four answer options and indicate the correct answer."
            )
        elif question_type == 'true/false':
            prompt = (
                f"Generate a realistic true/false interview question for a {difficulty} level "
                f"related to {topic}. Indicate the correct answer."
            )
        else:
            return {"error": "Invalid question type. Please use 'mcq' or 'true/false'."}

        try:
            # Call the OpenAI API using the new method
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",  # Use "gpt-4" if you have access
                messages=[{"role": "user", "content": prompt}],
                max_tokens=150
            )

            # Extract the generated content
            generated_content = response['choices'][0]['message']['content'].strip()
            questions.append(generated_content)

        except Exception as e:
            return {"error": str(e)}

    return questions

if __name__ == "__main__":
    # Example usage
    topic = "Python programming"
    difficulty = "medium"
    max_questions = 3
    question_type = "mcq"  # or "true/false"

    result = generate_interview_questions(topic, difficulty, max_questions, question_type)

    # Pretty print the result
    print(json.dumps(result, indent=2))