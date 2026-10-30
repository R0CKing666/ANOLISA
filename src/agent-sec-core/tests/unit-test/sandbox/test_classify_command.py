"""Command classification must not read a flag value as the subcommand."""

import unittest

from agent_sec_cli.sandbox.classify_command import CommandClassifier


class FlagValueSubcommandTests(unittest.TestCase):
    def setUp(self):
        self.classifier = CommandClassifier()

    def test_git_path_flags_keep_the_subcommand(self):
        expected = {
            "git -C /repo push": "default",
            "git --work-tree /repo pull": "default",
            "git -C /repo clean -fd": "dangerous",
            "git -C /repo status": "safe",
        }
        for command, decision in expected.items():
            with self.subTest(command=command):
                result = self.classifier.classify(command)
                self.assertEqual(result["decision"], decision, result)
                if decision == "default":
                    self.assertEqual(
                        result["additional_permissions"],
                        {"network": {"enabled": True}},
                    )

    def test_package_manager_registry_flags_keep_the_network_grant(self):
        for command in (
            "npm --registry https://r.example install pkg",
            "npm --registry=https://r.example install pkg",
            "pip --index-url https://r.example install pkg",
            "pip --index-url=https://r.example install pkg",
        ):
            with self.subTest(command=command):
                result = self.classifier.classify(command)
                self.assertEqual(result["decision"], "default", result)
                self.assertEqual(
                    result["additional_permissions"],
                    {"network": {"enabled": True}},
                )


if __name__ == "__main__":
    unittest.main()
