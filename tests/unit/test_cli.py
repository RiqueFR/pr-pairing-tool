import tempfile

import pytest

from pr_pairing import KnowledgeMode, merge_config
from pr_pairing.cli import parse_arguments


class TestParseArgs:
    def test_default_reviewers(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write("name,can_review\nAlice,true")
            temp_path = f.name

        try:
            import sys
            old_argv = sys.argv
            sys.argv = ['pr_pairing.py', '-i', temp_path]
            
            args = parse_arguments()
            args = merge_config({}, args)
            
            assert args.reviewers == 2
            assert args.team_mode is False
            assert args.knowledge_mode == KnowledgeMode.ANYONE.value
            
            sys.argv = old_argv
        finally:
            import os
            os.unlink(temp_path)

    def test_custom_reviewers(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write("name,can_review\nAlice,true")
            temp_path = f.name

        try:
            import sys
            old_argv = sys.argv
            sys.argv = ['pr_pairing.py', '-i', temp_path, '-r', '4']
            
            args = parse_arguments()
            
            assert args.reviewers == 4
            
            sys.argv = old_argv
        finally:
            import os
            os.unlink(temp_path)

    def test_team_mode_flag(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write("name,can_review\nAlice,true")
            temp_path = f.name

        try:
            import sys
            old_argv = sys.argv
            sys.argv = ['pr_pairing.py', '-i', temp_path, '-t']
            
            args = parse_arguments()
            
            assert args.team_mode is True
            
            sys.argv = old_argv
        finally:
            import os
            os.unlink(temp_path)

    def test_knowledge_mode_choices(self):
        modes = [
            (KnowledgeMode.ANYONE, "anyone"),
            (KnowledgeMode.EXPERTS_ONLY, "experts-only"),
            (KnowledgeMode.MENTORSHIP, "mentorship"),
            (KnowledgeMode.SIMILAR_LEVELS, "similar-levels"),
        ]
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write("name,can_review\nAlice,true")
            temp_path = f.name

        try:
            import sys
            old_argv = sys.argv
            
            for enum_mode, str_mode in modes:
                sys.argv = ['pr_pairing.py', '-i', temp_path, '-k', str_mode]
                args = parse_arguments()
                assert args.knowledge_mode == enum_mode.value
            
            sys.argv = old_argv
        finally:
            import os
            os.unlink(temp_path)
