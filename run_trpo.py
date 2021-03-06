from rllab.envs.box2d.cartpole_env import CartpoleEnv
from rllab.envs.normalized_env import normalize
from rllab.misc.instrument import stub, run_experiment_lite
from rllab.baselines.linear_feature_baseline import LinearFeatureBaseline
from rllab.envs.gym_env import GymEnv

from sandbox.rocky.tf.envs.base import TfEnv
from sandbox.rocky.tf.policies.gaussian_mlp_policy import GaussianMLPPolicy
from sandbox.rocky.tf.algos.trpo import TRPO
from rllab.misc import ext
from sandbox.rocky.tf.optimizers.conjugate_gradient_optimizer import ConjugateGradientOptimizer
from sandbox.rocky.tf.optimizers.conjugate_gradient_optimizer import FiniteDifferenceHvp

import pickle
import os.path as osp

import tensorflow as tf

import argparse
parser = argparse.ArgumentParser()
parser.add_argument("env", help="The environment name from OpenAIGym environments")
parser.add_argument("--num_epochs", default=100, type=int)
parser.add_argument("--batch_size", default=5000, type=int)
parser.add_argument("--step_size", default=0.01, type=float)
parser.add_argument("--reg_coeff", default=1e-5, type=float)
parser.add_argument("--gae_lambda", default=1.0, type=float)
parser.add_argument("--network_architecture", default=[100,50,25], type=int, nargs='*')
parser.add_argument("--data_dir", default="./data/")
parser.add_argument("--use_ec2", action="store_true", help="Use your ec2 instances if configured")
parser.add_argument("--dont_terminate_machine", action="store_false", help="Whether to terminate your spot instance or not. Be careful.")
parser.add_argument("--random_seed", default=1, type=int)
args = parser.parse_args()

stub(globals())
ext.set_seed(args.random_seed)

supported_gym_envs = ["MountainCarContinuous-v0", "InvertedPendulum-v1", "InvertedDoublePendulum-v1", "Hopper-v1", "Walker2d-v1", "Humanoid-v1", "Reacher-v1", "HalfCheetah-v1", "Swimmer-v1", "HumanoidStandup-v1"]

other_env_class_map  = { "Cartpole" :  CartpoleEnv}

if args.env in supported_gym_envs:
    gymenv = GymEnv(args.env, force_reset=True, record_video=False, record_log=False)
else:
    gymenv = other_env_class_map[args.env]()

#TODO: assert continuous space

env = TfEnv(normalize(gymenv))

print("Using network arch: %s" % ", ".join([str(x) for x in args.network_architecture]))

policy = GaussianMLPPolicy(
name="policy",
env_spec=env.spec,
# The neural network policy should have two hidden layers, each with 32 hidden units.
hidden_sizes=tuple([int(x) for x in args.network_architecture]),
hidden_nonlinearity=tf.nn.relu,
)

baseline = LinearFeatureBaseline(env_spec=env.spec)

algo = TRPO(
    env=env,
    policy=policy,
    baseline=baseline,
    batch_size=args.batch_size,
    max_path_length=env.horizon,
    n_itr=args.num_epochs,
    discount=0.99,
    step_size=args.step_size,
    gae_lambda=args.gae_lambda,
    optimizer=ConjugateGradientOptimizer(reg_coeff=args.reg_coeff, hvp_approach=FiniteDifferenceHvp(base_eps=args.reg_coeff))
)

arch_name="_".join([str(x) for x in args.network_architecture])
pref = "TRPO_" + args.env + "_bs_" + str(args.batch_size) + "_sp_" + str(args.step_size) + "_regc_" + str(args.reg_coeff) + "_gael_" + str(args.gae_lambda) + "_na_" + arch_name + "_seed_" + str(args.random_seed)
pref = pref.replace(".", "_")
print("Using prefix %s" % pref)

run_experiment_lite(
    algo.train(),
    log_dir=None if args.use_ec2 else args.data_dir,
    # Number of parallel workers for sampling
    n_parallel=1,
    # Only keep the snapshot parameters for the last iteration
    snapshot_mode="none",
    # Specifies the seed for the experiment. If this is not provided, a random seed
    # will be used
    exp_prefix=pref,
    seed=args.random_seed,
    mode="ec2" if args.use_ec2 else "local",
    plot=False,
    # dry=True,
    terminate_machine=args.dont_terminate_machine,
    added_project_directories=[osp.abspath(osp.join(osp.dirname(__file__), '.'))]
)
