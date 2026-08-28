## Gurobi Setup

### 1. Install Gurobi

```bash
python3 -m pip install gurobipy
```

Verify:

```bash
python3 -c "import gurobipy as gp; print(gp.gurobi.version())"
```

### 2. Get an Academic License

Go to:

https://www.gurobi.com/academia/academic-program-and-licenses/

Select **Named-User Academic** and generate the license.

After receiving your license key, run:

```bash
grbgetkey YOUR-LICENSE-KEY
```

### 3. Set the License

Suppose the license is saved at:

```text
~/Desktop/gurobi.lic
```

Set the license environment variable:

```bash
export GRB_LICENSE_FILE="$HOME/Desktop/gurobi.lic"
```

Verify:

```bash
echo $GRB_LICENSE_FILE
```

### 4. Test

```bash
python3 -c "import gurobipy as gp; m=gp.Model(); print('Gurobi OK')"
```

You should see:

```text
Gurobi OK
```

You should **not** see:

```text
Restricted license - for non-production use only
```

### 5. Make It Permanent

For `zsh`:

```bash
echo 'export GRB_LICENSE_FILE="$HOME/Desktop/gurobi.lic"' >> ~/.zshrc
source ~/.zshrc
```

### 6. Protect Your License

**Do not commit `gurobi.lic` to GitHub.**

Add it to `.gitignore`:

```gitignore
gurobi.lic
```
