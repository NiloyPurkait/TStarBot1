from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import sys
import os
import traceback
import time

import torch
from absl import app
from absl import flags
from absl import logging
import numpy as np

from sc2learner.envs.sc2_env import StarCraftIIEnv
from sc2learner.envs.actions.zerg_action_wrappers import ZergActionWrapper
from sc2learner.envs.observations.zerg_observation_wrappers import ZergObservationWrapper
from sc2learner.envs.observations.zerg_observation_wrappers import ZergNonspatialObservationWrapper
from sc2learner.envs.rewards.reward_wrappers import RewardShapingWrapperV2
from sc2learner.agents.random_agent import RandomAgent
from sc2learner.agents.keyboard_agent import KeyboardAgent
from sc2learner.agents.dqn_agent import DDQNAgent
from sc2learner.agents.models.sc2_networks import DuelingQNet
from sc2learner.agents.models.sc2_networks import NonspatialDuelingQNet
from sc2learner.agents.models.sc2_networks import NonspatialDuelingLinearQNet
from sc2learner.utils.utils import print_arguments


FLAGS = flags.FLAGS
flags.DEFINE_integer("num_episodes", 200, "Number of episodes to evaluate.")
flags.DEFINE_float("epsilon", 0.01, "Epsilon for policy.")
flags.DEFINE_integer("step_mul", 32, "Game steps per agent step.")
flags.DEFINE_enum("difficulty", '1',
                  ['1', '2', '3', '4', '5', '6', '7', '8', '9', 'A'],
                  "Bot's strength.")
flags.DEFINE_string("init_model_path", None, "Filepath to load initial model.")
flags.DEFINE_enum("agent", 'dqn', ['dqn', 'random', 'keyboard'], "Algorithm.")
flags.DEFINE_boolean("use_batchnorm", False, "Use batchnorm or not.")
flags.DEFINE_boolean("render", True, "Visualize feature map or not.")
flags.DEFINE_boolean("disable_fog", True, "Disable fog-of-war.")
flags.DEFINE_boolean("flip_features", True, "Flip 2D features.")
flags.DEFINE_boolean("use_reward_shaping", False, "Enable reward shaping.")
flags.DEFINE_boolean("use_spatial_features", True, "Use spatial features.")
flags.DEFINE_boolean("use_nonlinear_model", True, "Use Nonlinear model.")
flags.FLAGS(sys.argv)


def create_env(random_seed=None):
  env = StarCraftIIEnv(map_name='AbyssalReef',
                       step_mul=FLAGS.step_mul,
                       disable_fog=FLAGS.disable_fog,
                       resolution=16,
                       agent_race='zerg',
                       bot_race='zerg',
                       difficulty=FLAGS.difficulty,
                       visualize_feature_map=FLAGS.render,
                       random_seed=random_seed)
  if FLAGS.use_reward_shaping: env = RewardShapingWrapperV2(env)
  env = ZergActionWrapper(env)
  if FLAGS.use_spatial_features:
    env = ZergObservationWrapper(env, flip=FLAGS.flip_features)
  else:
    env = ZergNonspatialObservationWrapper(env)
  return env


def create_network(env):
  if FLAGS.use_spatial_features:
    assert FLAGS.use_nonlinear_model
    network = DuelingQNet(resolution=env.observation_space.spaces[0].shape[1],
                          n_channels=env.observation_space.spaces[0].shape[0],
                          n_dims=env.observation_space.spaces[1].shape[0],
                          n_out=env.action_space.n,
                          batchnorm=FLAGS.use_batchnorm)
  else:
    if FLAGS.use_nonlinear_model:
      network = NonspatialDuelingQNet(n_dims=env.observation_space.shape[0],
                                      n_out=env.action_space.n)
    else:
      network = NonspatialDuelingLinearQNet(
          n_dims=env.observation_space.shape[0],
          n_out=env.action_space.n)
  return network


def print_actions(env):
  print("----------------------------- Actions -----------------------------")
  for action_id, action_name in enumerate(env.action_names):
    print("Action ID: %d	Action Name: %s" % (action_id, action_name))
  print("-------------------------------------------------------------------")


def print_action_distribution(env, action_counts):
  print("----------------------- Action Distribution -----------------------")
  for action_id, action_name in enumerate(env.action_names):
    print("Action ID: %d	Count: %d	Name: %s" %
        (action_id, action_counts[action_id], action_name))
  print("-------------------------------------------------------------------")


def train():
  env = create_env(int(time.time()))
  print_actions(env)

  if FLAGS.agent == 'dqn':
    network = create_network(env)
    agent = DDQNAgent(observation_space=env.observation_space,
                      action_space=env.action_space,
                      network=network,
                      optimizer_type='adam',
                      learning_rate=0,
                      momentum=0.95,
                      adam_eps=1e-7,
                      batch_size=128,
                      discount=0.99,
                      eps_method='linear',
                      eps_start=0,
                      eps_end=0,
                      winning_rate_threshold=0,
                      difficulties=[],
                      mmc_beta=0,
                      mmc_discount=0,
                      eps_decay=5000000,
                      eps_decay2=30000000,
                      memory_size=1000000,
                      init_memory_size=100000,
                      frame_step_ratio=1.0,
                      gradient_clipping=1.0,
                      double_dqn=True,
                      target_update_freq=10000,
                      init_model_path=FLAGS.init_model_path)
  elif FLAGS.agent == 'random':
    agent = RandomAgent(action_space=env.action_space)
  elif FLAGS.agent == 'keyboard':
    agent = KeyboardAgent(action_space=env.action_space)
  else:
    raise NotImplementedError

  try:
    cum_return = 0.0
    action_counts = [0] * env.action_space.n
    for i in range(FLAGS.num_episodes):
      observation = env.reset()
      done = False
      step_id = 0
      while not done:
        action = agent.act(observation, eps=FLAGS.epsilon)
        print("Step ID: %d	Take Action: %d	Available Mask: %s" % (
            step_id, action, observation[-1]))
        observation, reward, done, _ = env.step(action)
        #print(observation[0].shape, observation[1].shape)
        action_counts[action] += 1
        #time.sleep(20)
        #time.sleep(0.3)
        cum_return += reward
        step_id += 1
      print_action_distribution(env, action_counts)
      print("Evaluated %d/%d Episodes Avg Return %f Avg Winning Rate %f" % (
          i + 1, FLAGS.num_episodes, cum_return / (i + 1),
          ((cum_return / (i + 1)) + 1) / 2.0))
  except KeyboardInterrupt: pass
  except: traceback.print_exc()
  env.close()


def main(argv):
  logging.set_verbosity(logging.ERROR)
  print_arguments(FLAGS)
  np.set_printoptions(threshold=np.nan, linewidth=500)
  train()


if __name__ == '__main__':
  app.run(main)