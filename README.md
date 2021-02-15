Benchmarking Scripts for MAGE
=============================
This repository contains a tool for benchmarking the MAGE system. The benchmarks are run primarily on Microsoft Azure (with some wide-area network experiments also using Google Cloud). The `magebench.py` tool allows one to spawn a virtual machines in the cloud, run benchmarks for MAGE using those virtual machines, collect log files containing the results of the benchmarks, and then deallocate those virtual machines. An IPython notebook, `graphs.ipynb` allows one to produce graphs based on the results, similar to the ones in the OSDI paper.

Setting up `magebench.py`
-------------------------
You will need a system that runs Python 3 to run this tool. This system serves as the "master" node that coordinates the benchmarks. It must remain connected to the Internet with a stable IP address for the duration of each experiment. Some of these experiments may take up to 24 hours to complete. If you can keep your laptop running with a stable Internet connection for that long (without going to standby sleep), then you can install and run this tool on your laptop. If not, you should use a server that has a stable Internet connection and run the tool on that machine.

Once you have chosen the machine, you must install the tool. It is recommended that you use a virtual environment, so that you can install the correct versions of the requisite Python libraries without affecting the system's Python configuration.

First, clone this repository and `cd` into it:
```
$ git clone https://github.com/ucbrise/mage-scripts
$ cd mage-scripts
```

Next, set up the virtual environment:
```
$ python3 -m venv ./magebench-venv
```

Then, activate the virtual environment:
```
$ source ./magebench-venv/bin/activate
```
You should now see `(magebench-venv)` at the start of each terminal prompt, indicating that the virtual environment is active in this terminal. If you run `python3` and import libraries, it will search for the libraries in the virtual environment. If you wish to stop using `magebench.py` (e.g., at the end of the day), you can run `deactivate`. Once you do this, `python3` will no longer use the virtual environment to search for libraries. If you deactivate the virtual environment or close this terminal, and wish to continue using `magebench.py`, then you should re-run the above command to re-activate the virtual environment before continuing to use `magebench.py`.

With the virtual environment active, install the requisite libraries in the virtual environment:
```
$ pip3 install -r requirements.txt
```
You only have to do this the _first_ time you use a virtual environment. If you close the terminal or run `deactivate` to stop using `magebench.py` temporarily, you do not have to re-run the above command when resuming experiments. You can just re-activate the virtual environment (`source ./magebench-venv/bin/activate`) and you'll be good to go.

The `magebench.py` program will attempt to allocate cloud resources using Microsoft Azure and Google Cloud. To do so, you need to set the appropriate environment variables so that `magebench.py` can authenticate to Microsoft Azure and Google Cloud. You should set the environment variables `AZURE_TENANT_ID`, `AZURE_CLIENT_ID`, and `AZURE_CLIENT_SECRET` to interact with Microsoft Azure, and `GOOGLE_APPLICATION_CREDENTIALS` to interact with Google Cloud. If you are a reviewer for OSDI Artifact Evaluation, you should have received authentication tokens that you can use for this step. Otherwise, you will need to set up users/apps linked to billing accounts for Microsoft Azure and Google Cloud to pay for the resources used.

Finally, you can run:
```
$ ./magebench.py -h
```
If all of the previous steps completed successfully, this should print usage information for the `magebench.py` command-line tool. There should be no Python error or traceback.
