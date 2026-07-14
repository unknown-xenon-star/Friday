import tensorflow as tf
from tensorflow.keras import layers, Sequential, Model

# ============================================================
# 1. Sequential API Example
# ============================================================
def create_sequential_model():
    model = Sequential([
        layers.Input(shape=(28, 28, 1)),
        layers.Conv2D(16, kernel_size=3, strides=1, padding='same', activation='relu'),
        layers.MaxPooling2D(pool_size=2, strides=2),
        layers.Flatten(),
        layers.Dense(64, activation='relu'),
        layers.Dropout(0.5),
        layers.Dense(10, activation='softmax')
    ])
    return model

# ============================================================
# 2. Functional API Example
# ============================================================
def create_functional_model():
    inputs = layers.Input(shape=(32, 32, 3))
    
    # Conv Block 1
    x = layers.Conv2D(32, kernel_size=3, strides=1, padding='valid', activation='relu')(inputs)
    x = layers.BatchNormalization()(x)
    x = layers.MaxPooling2D(pool_size=2)(x)
    
    # Conv Block 2
    x = layers.Conv2D(64, kernel_size=3, padding='same', activation='relu')(x)
    x = layers.Dropout(0.3)(x)
    
    # Classifier
    x = layers.Flatten()(x)
    x = layers.Dense(128, activation='relu')(x)
    outputs = layers.Dense(5)(x)
    
    return Model(inputs=inputs, outputs=outputs)

# ============================================================
# 3. Subclassed API Example
# ============================================================
class CustomFeatureExtractor(tf.keras.Model):
    def __init__(self):
        super(CustomFeatureExtractor, self).__init__()
        self.conv_1 = layers.Conv2D(32, kernel_size=5, padding='valid', activation='relu')
        self.conv_2 = layers.Conv2D(64, kernel_size=3, padding='same', activation='relu')
        self.pool = layers.MaxPooling2D(pool_size=2)
        self.flat = layers.Flatten()
        self.fc_1 = layers.Dense(32, activation='relu')
        
    def call(self, inputs):
        x = self.conv_1(inputs)
        x = self.pool(x)
        x = self.conv_2(x)
        x = self.pool(x)
        x = self.flat(x)
        return self.fc_1(x)

# Instantiate and build models
mnist_seq = create_sequential_model()
cifar_func = create_functional_model()

# Run data flow on subclassed model
sub_inputs = layers.Input(shape=(64, 64, 3))
extractor = CustomFeatureExtractor()
extracted_features = extractor(sub_inputs)
