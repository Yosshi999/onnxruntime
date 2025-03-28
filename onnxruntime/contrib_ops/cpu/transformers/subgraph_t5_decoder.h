// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT License.

#pragma once

#include "contrib_ops/cpu/transformers/subgraph_base.h"

namespace onnxruntime {
namespace contrib {
namespace transformers {

// A class for T5 decoder subgraph inputs and outputs preparation.
class T5DecoderSubgraph : public Subgraph {
 public:
  T5DecoderSubgraph(
      const onnxruntime::Node& node_in,
      const std::string& attribute_name,
      const GraphViewer& subgraph_in) : Subgraph(node_in, attribute_name, subgraph_in),
                                        has_hidden_state_(false) {
        first_present_output_index_ = 1;
      }

  // Create inputs for first inference of decoder subgraph.
  Status CreateInitialFeeds(
      gsl::span<const int32_t> beam_next_tokens,
      const std::vector<const OrtValue*>& implicit_inputs,
      const std::vector<OrtValue>& encoder_feeds,
      const std::vector<OrtValue>& encoder_fetches,
      std::vector<OrtValue>& decoder_feeds,
      const BeamSearchDeviceHelper::DeviceCopyFunc<int32_t>& device_copy_int32_func,
      void* stream);

  Status Validate(const std::vector<const NodeArg*>& subgraph_inputs,
                  const std::vector<const NodeArg*>& subgraph_outputs) override;

  void SetPastInputIndex(bool has_hidden_state) {
    has_hidden_state_ = has_hidden_state;
    if (!has_hidden_state_) {
      first_past_input_index_ = 2;
    } else {
      first_past_input_index_ = 3;
    }
  }

  int GetFirstPastInputIndex() const {
    return first_past_input_index_;
  }

  int GetFirstPresentOutputIndex() const {
    return first_present_output_index_;
  }

  int HasHiddenStates() const {
    return has_hidden_state_;
  }

 private:
  int first_past_input_index_;
  int first_present_output_index_;
  bool has_hidden_state_;
};

}  // namespace transformers
}  // namespace contrib
}  // namespace onnxruntime
