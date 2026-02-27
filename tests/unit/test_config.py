import tempfile
from pathlib import Path

import pytest

from pr_pairing import find_config_file, load_config, merge_config, FileError
from pr_pairing.cli import parse_arguments


class TestFindConfigFile:
    def test_find_config_explicit_path_exists(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("reviewers: 3\n")
            temp_path = f.name
        
        try:
            result = find_config_file(temp_path)
            assert result is not None
            assert result.name == Path(temp_path).name
        finally:
            import os
            os.unlink(temp_path)
    
    def test_find_config_explicit_path_not_exists(self):
        result = find_config_file("/nonexistent/config.yaml")
        assert result is None
    
    def test_find_config_no_path_returns_none_when_no_files(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        result = find_config_file(None)
        assert result is None
    
    def test_find_config_searches_prpairingrc(self, tmp_path, monkeypatch):
        config_file = tmp_path / ".prpairingrc"
        config_file.write_text("reviewers: 3\n")
        
        monkeypatch.chdir(tmp_path)
        result = find_config_file(None)
        assert result is not None
        assert result.name == ".prpairingrc"
    
    def test_find_config_searches_pr_pairing_yaml(self, tmp_path, monkeypatch):
        config_file = tmp_path / "pr_pairing.yaml"
        config_file.write_text("reviewers: 3\n")
        
        monkeypatch.chdir(tmp_path)
        result = find_config_file(None)
        assert result is not None
        assert result.name == "pr_pairing.yaml"
    
    def test_find_config_prpairingrc_priority_over_yaml(self, tmp_path, monkeypatch):
        config_file1 = tmp_path / ".prpairingrc"
        config_file1.write_text("reviewers: 3\n")
        config_file2 = tmp_path / "pr_pairing.yaml"
        config_file2.write_text("reviewers: 5\n")
        
        monkeypatch.chdir(tmp_path)
        result = find_config_file(None)
        assert result is not None
        assert result.name == ".prpairingrc"


class TestLoadConfig:
    def test_load_config_basic(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("reviewers: 3\nteam_mode: true\n")
            temp_path = f.name
        
        try:
            config = load_config(Path(temp_path))
            assert config["reviewers"] == 3
            assert config["team_mode"] is True
        finally:
            import os
            os.unlink(temp_path)
    
    def test_load_config_empty_file(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("")
            temp_path = f.name
        
        try:
            config = load_config(Path(temp_path))
            assert config == {}
        finally:
            import os
            os.unlink(temp_path)
    
    def test_load_config_invalid_yaml(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("invalid: yaml: content: [\n")
            temp_path = f.name
        
        try:
            with pytest.raises(FileError):
                load_config(Path(temp_path))
        finally:
            import os
            os.unlink(temp_path)


class TestMergeConfig:
    def test_merge_config_reviewers(self):
        import sys
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write("name,can_review\nAlice,true")
            temp_csv = f.name
        
        try:
            old_argv = sys.argv
            sys.argv = ['pr_pairing.py', '-i', temp_csv]
            
            args = parse_arguments()
            
            config = {"reviewers": 4}
            args = merge_config(config, args)
            
            assert args.reviewers == 4
            
            sys.argv = old_argv
        finally:
            import os
            os.unlink(temp_csv)
    
    def test_merge_config_team_mode_string(self):
        import sys
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write("name,can_review\nAlice,true")
            temp_csv = f.name
        
        try:
            old_argv = sys.argv
            sys.argv = ['pr_pairing.py', '-i', temp_csv]
            
            args = parse_arguments()
            
            config = {"team_mode": "true"}
            args = merge_config(config, args)
            
            assert args.team_mode is True
            
            sys.argv = old_argv
        finally:
            import os
            os.unlink(temp_csv)
    
    def test_merge_config_knowledge_mode(self):
        import sys
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write("name,can_review\nAlice,true")
            temp_csv = f.name
        
        try:
            old_argv = sys.argv
            sys.argv = ['pr_pairing.py', '-i', temp_csv]
            
            args = parse_arguments()
            
            config = {"knowledge_mode": "mentorship"}
            args = merge_config(config, args)
            
            assert args.knowledge_mode == "mentorship"
            
            sys.argv = old_argv
        finally:
            import os
            os.unlink(temp_csv)
    
    def test_merge_config_history(self):
        import sys
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write("name,can_review\nAlice,true")
            temp_csv = f.name
        
        try:
            old_argv = sys.argv
            sys.argv = ['pr_pairing.py', '-i', temp_csv]
            
            args = parse_arguments()
            
            config = {"history": "./custom_history.json"}
            args = merge_config(config, args)
            
            assert args.history == "./custom_history.json"
            
            sys.argv = old_argv
        finally:
            import os
            os.unlink(temp_csv)
    
    def test_merge_config_verbose_bool(self):
        import sys
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write("name,can_review\nAlice,true")
            temp_csv = f.name
        
        try:
            old_argv = sys.argv
            sys.argv = ['pr_pairing.py', '-i', temp_csv]
            
            args = parse_arguments()
            
            config = {"verbose": True}
            args = merge_config(config, args)
            
            assert args.verbose == 1
            
            sys.argv = old_argv
        finally:
            import os
            os.unlink(temp_csv)
    
    def test_merge_config_verbose_int(self):
        import sys
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write("name,can_review\nAlice,true")
            temp_csv = f.name
        
        try:
            old_argv = sys.argv
            sys.argv = ['pr_pairing.py', '-i', temp_csv]
            
            args = parse_arguments()
            
            config = {"verbose": 2}
            args = merge_config(config, args)
            
            assert args.verbose == 2
            
            sys.argv = old_argv
        finally:
            import os
            os.unlink(temp_csv)
    
    def test_merge_config_cli_overrides_config(self):
        import sys
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write("name,can_review\nAlice,true")
            temp_csv = f.name
        
        try:
            old_argv = sys.argv
            sys.argv = ['pr_pairing.py', '-i', temp_csv, '-r', '5']
            
            args = parse_arguments()
            
            config = {"reviewers": 3}
            args = merge_config(config, args)
            
            assert args.reviewers == 5
            
            sys.argv = old_argv
        finally:
            import os
            os.unlink(temp_csv)
    
    def test_merge_config_cli_team_mode_overrides_config(self):
        import sys
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write("name,can_review\nAlice,true")
            temp_csv = f.name
        
        try:
            old_argv = sys.argv
            sys.argv = ['pr_pairing.py', '-i', temp_csv, '-t']
            
            args = parse_arguments()
            
            config = {"team_mode": False}
            args = merge_config(config, args)
            
            assert args.team_mode is True
            
            sys.argv = old_argv
        finally:
            import os
            os.unlink(temp_csv)
    
    def test_merge_config_exclude_list(self):
        import sys
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write("name,can_review\nAlice,true")
            temp_csv = f.name
        
        try:
            old_argv = sys.argv
            sys.argv = ['pr_pairing.py', '-i', temp_csv]
            
            args = parse_arguments()
            
            config = {"exclude": ["Alice:Bob", "Charlie:Dana"]}
            args = merge_config(config, args)
            
            assert args.exclude == ["Alice:Bob", "Charlie:Dana"]
            
            sys.argv = old_argv
        finally:
            import os
            os.unlink(temp_csv)
    
    def test_merge_config_require_list(self):
        import sys
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write("name,can_review\nAlice,true")
            temp_csv = f.name
        
        try:
            old_argv = sys.argv
            sys.argv = ['pr_pairing.py', '-i', temp_csv]
            
            args = parse_arguments()
            
            config = {"require": ["Bob:Alice", "Charlie:Bob"]}
            args = merge_config(config, args)
            
            assert args.require == ["Bob:Alice", "Charlie:Bob"]
            
            sys.argv = old_argv
        finally:
            import os
            os.unlink(temp_csv)
    
    def test_merge_config_strict(self):
        import sys
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write("name,can_review\nAlice,true")
            temp_csv = f.name
        
        try:
            old_argv = sys.argv
            sys.argv = ['pr_pairing.py', '-i', temp_csv]
            
            args = parse_arguments()
            
            config = {"strict": True}
            args = merge_config(config, args)
            
            assert args.strict is True
            
            sys.argv = old_argv
        finally:
            import os
            os.unlink(temp_csv)
    
    def test_merge_config_output(self):
        import sys
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write("name,can_review\nAlice,true")
            temp_csv = f.name
        
        try:
            old_argv = sys.argv
            sys.argv = ['pr_pairing.py', '-i', temp_csv]
            
            args = parse_arguments()
            
            config = {"output": "output.csv"}
            args = merge_config(config, args)
            
            assert args.output == "output.csv"
            
            sys.argv = old_argv
        finally:
            import os
            os.unlink(temp_csv)
    
    def test_merge_config_output_format(self):
        import sys
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write("name,can_review\nAlice,true")
            temp_csv = f.name
        
        try:
            old_argv = sys.argv
            sys.argv = ['pr_pairing.py', '-i', temp_csv]
            
            args = parse_arguments()
            
            config = {"output_format": "json"}
            args = merge_config(config, args)
            
            assert args.output_format == "json"
            
            sys.argv = old_argv
        finally:
            import os
            os.unlink(temp_csv)
    
    def test_merge_config_quiet(self):
        import sys
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write("name,can_review\nAlice,true")
            temp_csv = f.name
        
        try:
            old_argv = sys.argv
            sys.argv = ['pr_pairing.py', '-i', temp_csv]
            
            args = parse_arguments()
            
            config = {"quiet": 1}
            args = merge_config(config, args)
            
            assert args.quiet == 1
            
            sys.argv = old_argv
        finally:
            import os
            os.unlink(temp_csv)
