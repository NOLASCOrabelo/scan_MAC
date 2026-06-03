import unittest
from unittest.mock import MagicMock, patch
import sys

# Mock sys.modules before importing agent to avoid actually loading GenAI during import
sys.modules['google'] = MagicMock()
sys.modules['google.genai'] = MagicMock()
sys.modules['playwright'] = MagicMock()
sys.modules['playwright.sync_api'] = MagicMock()

# Mock file loading for instructions
with patch("builtins.open", unittest.mock.mock_open(read_data="system instruction mock")):
    import agent

class TestAgentLanguages(unittest.TestCase):
    @patch('agent.client')
    def test_gerar_comentario_pt_br(self, mock_genai_client):
        # Setup mock response
        mock_response = MagicMock()
        mock_response.text = "Comentário em português"
        mock_genai_client.models.generate_content.return_value = mock_response

        # Call function
        result = agent.gerar_comentario("Post de teste", idioma="pt-BR")

        # Verify result
        self.assertEqual(result, "Comentário em português")
        
        # Verify prompt details
        call_args = mock_genai_client.models.generate_content.call_args
        prompt_arg = call_args[1]['contents']
        self.assertIn("Portuguese", prompt_arg)
        self.assertIn("Brazilian Portuguese", prompt_arg)

    @patch('agent.client')
    def test_gerar_comentario_en_us(self, mock_genai_client):
        # Setup mock response
        mock_response = MagicMock()
        mock_response.text = "Comment in English"
        mock_genai_client.models.generate_content.return_value = mock_response

        # Call function
        result = agent.gerar_comentario("Post de teste", idioma="en-US")

        # Verify result
        self.assertEqual(result, "Comment in English")
        
        # Verify prompt details
        call_args = mock_genai_client.models.generate_content.call_args
        prompt_arg = call_args[1]['contents']
        self.assertIn("English", prompt_arg)
        self.assertIn("US English", prompt_arg)

if __name__ == "__main__":
    unittest.main()
