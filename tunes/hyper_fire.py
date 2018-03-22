import os
import time
import random
import re

job_name_prefix = 'zerg_dqn_duel_adam_e2'
save_model_dir = '/out/checkpoints'
save_log_path = '/out/log'
log_dir = 'logs'
local_log = 'hyper.log'
exps_num = 20
rand_patterns = {'learning_rate':['log-uniform', -7, -5]}


def gen_random_hypers(rand_patterns):
    conf = ""
    for param_name, pattern in rand_patterns.items():
        if pattern[0] == 'uniform':
            assert len(pattern) == 3, "Type 'uniform' requires 2 arguments"
            value = random.uniform(pattern[1], pattern[2])
            conf += " --%s %g" % (param_name, value)
        elif pattern[0] == 'log-uniform':
            assert len(pattern) == 3, "Type 'log-uniform' requires 2 arguments."
            value = pow(10.0, random.uniform(pattern[1], pattern[2]))
            conf += " --%s %g" % (param_name, value)
        elif pattern[0] == 'enum':
            value = random.choice(pattern[1:])
            conf += " --%s %s" % (param_name, value)
        elif pattern[0] == 'bool':
            value = random.choice([0, 1])
            if value == 1:
                conf += " --%s" % param_name
            else:
                conf += " --no%s" % param_name
        else:
            assert False, "Type %s not supported." % pattern[0]
    return conf


def allocate_resources(conf):
    items = [item.split() for item in re.split(" --", conf)
             if len(item.split()) == 2]
    items_map = {k:v for k, v in items}
    mem = int(items_map['memory_size']) / 2500 + 4
    return mem, cpu


def hyper_tune(exp_id):
    conf = gen_random_hypers(rand_patterns)
    mem, cpu = 83, 20
    conf += ' --save_model_dir %s' % os.path.join(save_model_dir,
                                                  'checkpoints_%d' % exp_id)
    log_path = os.path.join(log_dir, 'log_%d' % exp_id)
    job_name = '%s-%d' % (job_name_prefix, exp_id)
    cmds = ('fire run --mem %dg --cpu %d --gpu 1 --mark %d '
            '--name %s '
            '--up sc2lab '
            '--disk balderli/sc2_core '
            'install_and_run.sh "%s" %s > %s 2>&1 &'
            % (mem, cpu, exp_id, job_name, conf, save_log_path, log_path))
    assert os.system(cmds) == 0
    time.sleep(1.0)
    output = os.popen('fire id --mark %d ' % exp_id)
    jobid = output.read().strip()
    print("Job-%d-%s %s\n" % (exp_id, jobid, cmds))
    return jobid, cmds


if __name__ == '__main__':
    if not os.path.isdir(log_dir):
        os.mkdir(log_dir)

    with open(local_log, 'wt') as f:
        for i in range(exps_num):
            jobid, cmds = hyper_tune(i)
            f.write("Job-%d-%s %s\n" % (i, jobid, cmds))
