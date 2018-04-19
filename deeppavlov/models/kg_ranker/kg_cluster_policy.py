"""
Copyright 2017 Neural Networks and Deep Learning lab, MIPT

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

import collections
import numpy as np

from deeppavlov.core.models.component import Component
from deeppavlov.core.common.registry import register


@register('kg_cluster_policy')
def KudaGoClusterPolicyManager(Component):
    def __init__(self, slots, tags=None, min_rate=0.01, max_rate=0.99,
                 *args, **kwargs):
        clusters = {cl_id: val[1:] for cl_id, val in slots.items()
                    if val[0] == 'ClusterSlot'}
        self.questions_d = {cl_id: q for cl_id, (q, tags) in clusters.items()}
        self.min_rate = min_rate
        self.max_rate = max_rate
        self.tags_l = tags

        if self.tags_l is None:
            self.tags_l = list(set(t for q, tags in clusters.values() for t in tags))
        # clusters: (num_clusters, num_tags)
        self.clusters_oh = {cl_id: self._onehot([tags], self.tags_l)
                            for cl_id, (q, tags) in clusters.items()}

    @staticmethod
    def _onehot(tags, all_tags):
        """
        tags: list of lists of str tags
        all_tags: list of str tags
        Returns: np.array (num_samples, num_tags)
        """
        num_samples, num_tags = len(tags), len(all_tags)
        onehoted = np.zeros((num_samples, num_tags))
        for i, s_tags in enumerate(tags):
            s_filtered_tags = set.intersection(set(s_tags), set(all_tags))
            for t in s_filtered_tags:
                onehoted[i, all_tags.index(t)] = 1
        return onehoted

    def __call__(self, events):
        event_tags_l = [e['tags'] for e in events if e['tags']]
        event_tags_oh = self._onehot(event_tags_l, self.tags_l)

        bst_cluster_id, bst_rate = self._best_divide(event_tags_oh)
        if (bst_rate < self.min_rate) or (bst_rate > self.max_rate):
            return "", None
        return self.questions[bst_cluster_id], bst_cluster_id

    def _best_divide(self, event_tags_oh):
        """
        event_tags_oh: np.array (num_samples, num_tags)
        Returns: cluster_id, divide_rate
        """
        cluster_ids = []
        split_rates = []
        num_events = self._num_events_with_tags(event_tags_oh)
        for cl_id, cl_oh in self.clusters_oh.items():
            cluster_ids.append(cl_id)
            split_event_tags_oh = self._split_by_tags(event_tags_oh, cl_oh)
            num_split_events = self._num_events_with_tags(split_event_tags_oh)
            split_rates.append(num_split_events / num_events)
        best_idx = np.argmin(np.fabs(0.5 - np.array(split_rates)))
        return cluster_ids[best_idx], split_rates[best_idx]

    @staticmethod
    def _split_by_tags(event_tags_oh, tags_oh):
        """
        event_tags_oh: np.array (num_samples x num_tags)
        tags_oh: np.array (num_tags x 1) or (num_tags)
        Returns:
            np.array (num_samples x num_tags)
        """
        return np.multiply(event_tags_oh, tags_oh)

    @staticmethod
    def _num_nonnull_events(event_tags_oh):
        """
        event_tags_oh: np.array (num_samples x num_tags)
        Returns:
            int
        """
        return np.sum(np.sum(event_tags_oh, axis=1) > 0)