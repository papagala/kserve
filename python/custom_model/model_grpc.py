# Copyright 2022 The KServe Authors.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import io
from typing import Dict
import numpy as np

import kserve
import torch
from kserve.grpc.grpc_predict_v2_pb2 import ModelInferRequest
from kserve.utils.utils import generate_uuid
from PIL import Image
from torchvision import models, transforms


# This custom predictor example implements the custom model following KServe v2 inference gPPC protocol,
# the input can be raw image bytes or image tensor which is pre-processed by transformer
# and then passed to predictor, the output is the prediction response.
class AlexNetModel(kserve.Model):
    def __init__(self, name: str):
        super().__init__(name)
        self.name = name
        self.load()
        self.model = None
        self.ready = False

    def load(self):
        self.model = models.alexnet(pretrained=True)
        self.model.eval()
        self.ready = True

    def preprocess(self, payload: ModelInferRequest, headers: Dict[str, str] = None) -> torch.Tensor:
        req = payload.inputs[0]
        if req.datatype == "BYTES":
            raw_img_data = req.contents.bytes_contents[0]
            input_image = Image.open(io.BytesIO(raw_img_data))
            preprocess = transforms.Compose([
                transforms.Resize(256),
                transforms.CenterCrop(224),
                transforms.ToTensor(),
                transforms.Normalize(mean=[0.485, 0.456, 0.406],
                                     std=[0.229, 0.224, 0.225]),
            ])

            input_tensor = preprocess(input_image)
            return input_tensor.unsqueeze(0)
        elif req.datatype == "FP32":
            result = np.frombuffer(payload.raw_input_contents[0], dtype="float32")
            batched_result = np.reshape(result, req.shape)
            return torch.Tensor(batched_result)

    def predict(self, input_tensor: torch.Tensor, headers: Dict[str, str] = None) -> Dict:
        output = self.model(input_tensor)
        torch.nn.functional.softmax(output, dim=1)
        values, top_5 = torch.topk(output, 5)
        result = values.tolist()
        id = generate_uuid()
        response = {
            "id": id,
            "model_name": "custom-model",
            "outputs": [
                {
                    "contents": {
                        "fp32_contents": result[0],
                    },
                    "datatype": "FP32",
                    "name": "output-0",
                    "shape": list(values.shape)
                }
            ]}
        return response


if __name__ == "__main__":
    model = AlexNetModel("custom-model")
    model.load()
    kserve.ModelServer().start([model])
