import torch
import torch.nn as nn
from torchvision import models, transforms  # Import models here
from PIL import Image
import numpy as np
import os
from typing import Dict

# Initialize the model path
script_dir = os.path.dirname(os.path.abspath(__file__))
model_path = os.path.abspath(os.path.join(script_dir, "..", "..", "model", "best_shoe_model.pth"))


# === Your model class (same as training) ===
class MultiOutputShoeModelResNet18(nn.Module):
    def __init__(self, n_outputs):
        super(MultiOutputShoeModelResNet18, self).__init__()
        self.base = models.resnet18(pretrained=False)
        self.base.fc = nn.Identity()

        for param in self.base.parameters():
            param.requires_grad = False
        for param in self.base.layer4.parameters():
            param.requires_grad = True

        self.fc_layers = nn.ModuleDict()
        for col in n_outputs:
            self.fc_layers[col] = nn.Sequential(
                nn.Linear(512, 1024),
                nn.BatchNorm1d(1024),
                nn.ReLU(),
                nn.Dropout(0.5),
                nn.Linear(1024, 512),
                nn.BatchNorm1d(512),
                nn.ReLU(),
                nn.Dropout(0.3),
                nn.Linear(512, n_outputs[col])
            )

    def forward(self, x):
        features = self.base(x)
        return {col: self.fc_layers[col](features) for col in n_outputs}


# === Load the model checkpoint ===
checkpoint = torch.load(model_path, map_location='cpu', weights_only=False)

# Extract the number of outputs for each column from the checkpoint
n_outputs = {col: len(checkpoint['label_encoders'][col].classes_) for col in checkpoint['columns']}

# Initialize the model and load the state_dict
model = MultiOutputShoeModelResNet18(n_outputs)
model.load_state_dict(checkpoint['model_state_dict'])
model.eval()

# Label encoders and column names from the checkpoint
label_encoders = checkpoint['label_encoders']
columns = checkpoint['columns']
# ✅ Define transform globally (outside the function)
transform = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.485, 0.456, 0.406],
                         std=[0.229, 0.224, 0.225])
])



def predict_model_properties(rgba_array: np.ndarray) -> Dict[str, Dict[str, str]]:
    """
    Predict advanced shoe properties using your trained multi-output ResNet18 model.
    Converts RGBA array to PIL Image -> applies transformations -> model predicts.
    Skips preprocessing since the shoe is already cropped by YOLO.
    """
    try:
        # Convert RGBA numpy array to PIL Image (ignore alpha channel)
        img = Image.fromarray((rgba_array[:, :, :3]).astype(np.uint8), mode='RGB')

        # Apply correct preprocessing: resize + normalize
        img_tensor = transform(img).unsqueeze(0)

        with torch.no_grad():
            outputs = model(img_tensor)

        predicted_labels = {}
        for col in columns:
            # Apply softmax to get probabilities
            probs = torch.softmax(outputs[col], dim=1)
            confidence, predicted_idx = torch.max(probs, 1)

            label = label_encoders[col].inverse_transform(predicted_idx.cpu().numpy())[0]
            confidence_percent = f"{confidence.item() * 100:.1f}"  # e.g., '94.6%'

            predicted_labels[col] = {
                "label": label,
                "confidence": confidence_percent
            }

        return predicted_labels

    except Exception as e:
        print(f"Model prediction error: {e}")
        return {}
#
# # Test it by calling the function with an RGBA array (cropped shoe image from YOLO)
# if __name__ == "__main__":
#     # Placeholder example, replace with actual RGBA data from YOLO
#     rgba_array = np.random.rand(224, 224, 4) * 255  # Example RGBA array
#     result = predict_model_properties(rgba_array)
#     print("Predicted Shoe Attributes with Confidence:")
#     print(result)
