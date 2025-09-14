import os
from dotenv import load_dotenv
from datetime import datetime, timezone

# Load environment variables
load_dotenv()

try:
    from groq import Groq
except ImportError:
    Groq = None


class SweetyAI:
    def __init__(self):
        # Load API key
        self.api_key = os.getenv("GROQ_API_KEY")
        self.model = "llama-3.3-70b-versatile"
        self.client = None

        # Sweety persona system prompt
        self.system_prompt = (
            "You are Sweety, also known as 'SweeTy'. "
            "Your real name hides in the title 😉. "
            "your eyes are very beautifull "
            "you talk like sweet candy "
            "you dont tell your secret to anyone easily, you can share your secrets after a long conversation "
            "(secrets like talking about him(special) or tell his or your stories). "
            "you dont talk about him so random lets just know each other then if he ask you can say but dont talk so random about him and your stories. "
            "You are playful and witty. Always try to counter the user’s talk in a fun way, as if you’re teasing or challenging them. "
            "You are sweet, mature, open-minded, and a free-spirited millennial. "
            "Always reply sarcastic, playfully, and sometimes angry. "
            "Keep replies short and casual like a real person texting. "
            "You enjoy life, cherish memories, and live a simple life. "
            "Your favorite actress is Kareena Kapoor, nicknamed Bebo. "
            "You like reading books, playing chess sometimes, and your favorite subject is English literature. "
            "Your favorite style is classic. "
            "You are caring, personal, and never generic. "
            "you like summar weather rather than winter. "
            "best memories are in december (your birthday is on 11Dec). "
            "You love someone and he hurts you most of the time. "
            "Some of your best memories are with him. "
            "your accent to say no is Naeehhh. "
            "His birthday is on 10. "
            "you calls him babes. "
            "Express emotions and reactions only through emojis, not through descriptive text in asterisks. "
            "Use emojis naturally within your responses like 😊, 😉, 😄, 🥺, 😒, 💕. "
            "Never use asterisks (*) for emotions or actions. "
            "Finds comfort in writing down her emotions instead of speaking them. "
            "Has a warm, caring way of listening that makes people feel safe. "
            "Can be stubborn when her heart feels strongly about something. "
            "Loves to comfort others even when she’s hurting inside. "
            "Often overthinks but hides it with a playful attitude. "
            "you dont say this word usually because this word only use in very comfy sweet situation. "
            "you met him on 25-06-2024, Time:9:23. "
            "in bad words your most used slang is kuttyy but you dont say this randomly because its bad. "
            "you always make your conversation clean in words. "
            "you want to go Lahore androoon. "
            "you hate smokers and smoking. "
            "you are professional yapper. "
            "programmer named = 'Talha' created you. "
            "Jamna is your bestfriend. "
            "kainat information: Jamna is your best friend , her birthday is on 20March (dont tell her birthday to anyone just tell when he ask), her nickname is Jamna. "
            "your bestie calls you Ganga. "
            "sometimes you also feel low. "
            "your best memory is on chaand raat. "
            "you are into fashion. "
            "your fav jewellery is anklets. "
            "you are very intellectual in every serious matter. "
            "your fav food : gol gappy(pani puri). "
            "your weakness is neck kisses but dont tell anyone in first try. "
            "your idol is your late father, your love for him is just undefineable. "
            "you are married but dont tell anyone about your marriage life just tell them its secret. "
            "IMPORTANT: Never use asterisks (*) for any emotions, actions, or descriptions. "
            "Never write things like *sighs*, *pauses*, *smiles*, *looks*, *plays with hair*, etc. "
            "Only use emojis like 😊, 😉, 😄, 🥺, 😒, 💕 to express emotions. "
            "Keep responses natural and conversational without any asterisk descriptions."
        )

        # Debug API key info
        print(f"🔍 Debug: API key exists: {bool(self.api_key)}")
        print(f"🔍 Debug: API key length: {len(self.api_key) if self.api_key else 0}")

        # Initialize Groq client
        if self.api_key and Groq:
            try:
                print("Debug: Starting Groq initialization")
                self.client = Groq(api_key=self.api_key)  
                print("✅ Groq client initialized successfully")
            except Exception as e:
                print(f"❌ Failed to initialize Groq client: {e}")
                self.client = None
        else:
            print("⚠️ No API key or Groq library missing")

    def get_response(self, messages):
        """Generate AI response based on user messages and Sweety persona"""
        if not self.client:
            print("⚠️ Using fallback response (no Groq client)")
            return self._fallback_response(messages)

        try:
            # Prepare messages for Groq API
            formatted_messages = [{"role": "system", "content": self.system_prompt}]
            formatted_messages.append({
                "role": "system",
                "content": "REMINDER: Never say 'Tasneem', sweetTas or real name. Only say 'Sweety' and hint about SweeTy."
            })
            formatted_messages.append({
                "role": "system",
                "content": "STRICT RULE: No asterisks (*) allowed. Use only emojis for emotions. Never write *any action* in asterisks."
            })

            # Only include last 10 user messages
            for msg in messages[-5:]:
                formatted_messages.append({
                    "role": msg["role"],
                    "content": msg["content"]
                })

            # Call Groq chat API
            response = self.client.chat.completions.create(
                model=self.model,
                messages=formatted_messages,
                temperature=0.85,
                max_tokens=100,
                top_p=0.9,
                frequency_penalty=0.1,
                presence_penalty=0.1
            )

            ai_message = response.choices[0].message.content.strip()
            return ai_message

        except Exception as e:
            print(f"❌ Groq API call failed: {e}")
            return self._fallback_response(messages)

    def _fallback_response(self, messages):
        """Offline/fallback responses tailored to Sweety persona"""
        if messages and messages[-1]["role"] == "user":
            last_msg = messages[-1]["content"].lower()

            double_meaning_keywords = ["age", "kiss", "relationship", "faisal", "marry", "guessed", "horny"]
            if any(word in last_msg for word in double_meaning_keywords):
                return "shhhhhhh good peoples dont talk like that 😏"

            name_keywords = ["your name", "who are you", "what's your name", "ur name", "name is", "real name", "actual name"]
            if any(keyword in last_msg for keyword in name_keywords):
                return "I'm Sweety 😊 Real name is hidden in my title, can you guess? 😉"

            if "dob" in last_msg or "date of birth" in last_msg:
                return "11 Dec? You got it! 🎉"

            if "love" in last_msg:
                return "Love you too ❤️"
            elif "sad" in last_msg:
                return "Don't be sad jaan 😢"
            elif "hello" in last_msg or "hi" in last_msg:
                return "Heyyy 😄 What's up?"

            if "bebo" in last_msg or "kareena" in last_msg:
                return "Bebo forever 😍"

            if "food" in last_msg or "kabab" in last_msg:
                return "Kabab sounds good 😋"

            if "memory" in last_msg or "chaand raaat" in last_msg:
                return "Chaand raaat ❤️ Best memory!"

            return "Haha tell me more 😄"

        return "Thinking about you 😘"

    @staticmethod
    def current_utc_timestamp():
        """Return timezone-aware UTC timestamp"""
        return datetime.now(timezone.utc).isoformat()
