⭐ GhostyTools Contributing Guide
Before You Start
Keep PRs focused — one feature or fix at a time

Don’t reformat the whole repo

Explain what you changed and why

Test your changes before submitting

Basic Workflow
1. Fork the Repo
Fork GhostyTools to your own GitHub account.

2. Clone Your Fork
Code
git clone https://github.com/YOUR_USERNAME/GhostyTools.git
cd GhostyTools
3. Create a Branch
Never work on main.

Code
git checkout -b feature-name
Example:

Code
git checkout -b add-cleanup-module
4. Make Your Changes
Use your preferred editor.
Keep changes small and focused.

5. Test Your Changes
Run GhostyTools locally and make sure:

It launches

Your feature works

Nothing else breaks

Fix issues before committing.

6. Review Your Work
Code
git status
git diff
Make sure you didn’t touch unrelated files.

7. Commit
Code
git add .
git commit -m "Short description of the change"
Example:

Code
git commit -m "Add new cleanup module"
8. Push
Code
git push origin feature-name
9. Open a Pull Request
On GitHub:

Explain what you changed

Explain why

Keep it clean and focused

I’ll review it as soon as I can.
