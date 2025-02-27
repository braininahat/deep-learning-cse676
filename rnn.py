import glob
import os
import librosa
import matplotlib.pyplot as plt
import tensorflow as tf
from tensorflow.python.ops import rnn, rnn_cell
import numpy as np
from tensorflow.contrib import cudnn_rnn

plt.style.use('ggplot')


def windows(data, window_size):
    start = 0
    while start < len(data):
        yield int(start), int(start + window_size)
        start += (window_size / 2)


def extract_features(parent_dir, sub_dirs, file_ext="*.wav", bands=20, frames=41):
    window_size = 512 * (frames - 1)
    mfccs = []
    labels = []
    for l, sub_dir in enumerate(sub_dirs):
        for fn in glob.glob(os.path.join(parent_dir, sub_dir, file_ext)):
            print(fn)
            sound_clip, s = librosa.load(fn)
            label = fn.split('/')[3].split('-')[1]
            for (start, end) in windows(sound_clip, window_size):
                if(len(sound_clip[start:end]) == window_size):
                    signal = sound_clip[start:end]
                    mfcc = librosa.feature.mfcc(y=signal, sr=s, n_mfcc=bands).T.flatten()[:, np.newaxis].T
                    mfccs.append(mfcc)
                    labels.append(label)
    features = np.asarray(mfccs).reshape(len(mfccs), frames, bands)
    return np.array(features), np.array(labels, dtype=np.int)


def one_hot_encode(labels):
    n_labels = len(labels)
    n_unique_labels = len(np.unique(labels))
    one_hot_encode = np.zeros((n_labels, n_unique_labels))
    one_hot_encode[np.arange(n_labels), labels] = 1
    return one_hot_encode


parent_dir = 'UrbanSound8K/audio/'
sub_dirs = ['fold1', 'fold2', 'fold3',
            'fold4', 'fold5', 'fold6',
            'fold7', 'fold8', 'fold9',
            'fold10']
features, labels = extract_features(parent_dir, sub_dirs)
labels = one_hot_encode(labels)


rnd_indices = np.random.rand(len(labels)) < 0.70

tr_features = features[rnd_indices]
tr_labels = labels[rnd_indices]
ts_features = features[~rnd_indices]
ts_labels = labels[~rnd_indices]


tf.reset_default_graph()

learning_rate = 0.01
training_iters = 1000
batch_size = 50
display_step = 200

# Network Parameters
n_input = 20
n_steps = 41
n_hidden = 300
n_classes = 10

x = tf.placeholder("float", [None, n_steps, n_input])
y = tf.placeholder("float", [None, n_classes])

weight = tf.Variable(tf.random_normal([n_hidden, n_classes]))
bias = tf.Variable(tf.random_normal([n_classes]))
epoch = 2000


def RNN(x, weight, bias):
    cell = rnn_cell.LSTMCell(num_units=n_hidden)
    # cells = rnn_cell.MultiRNNCell(cell)
    output, state = tf.nn.dynamic_rnn(cell, x, dtype=tf.float32)
    output = tf.transpose(output, [1, 0, 2])
    last = tf.gather(output, int(output.get_shape()[0]) - 1)
    return tf.nn.softmax(tf.matmul(last, weight) + bias)


prediction = RNN(x, weight, bias)

# Define loss and optimizer
loss_f = -tf.reduce_sum(y * tf.log(prediction))
optimizer = tf.train.AdamOptimizer(learning_rate=learning_rate).minimize(loss_f)

# Evaluate model
correct_pred = tf.equal(tf.argmax(prediction, 1), tf.argmax(y, 1))
accuracy = tf.reduce_mean(tf.cast(correct_pred, tf.float32))

# Initializing the variables
init = tf.global_variables_initializer()


# In[ ]:


with tf.Session() as session:
    writer = tf.summary.FileWriter('graphs/rnn/', session.graph)
    session.run(init)
    for itr in range(training_iters):
        offset = (itr * batch_size) % (tr_labels.shape[0] - batch_size)
        batch_x = tr_features[offset:(offset + batch_size), :, :]
        batch_y = tr_labels[offset:(offset + batch_size), :]
        _, c = session.run([optimizer, loss_f], feed_dict={x: batch_x, y: batch_y})

        if epoch % display_step == 0:
            # Calculate batch accuracy
            acc = session.run(accuracy, feed_dict={x: batch_x, y: batch_y})
            # Calculate batch loss
            loss = session.run(loss_f, feed_dict={x: batch_x, y: batch_y})
            print("Iter " + str(epoch) + ", Minibatch Loss= " + "{:.6f}".format(loss) + ", Training Accuracy= " + "{:.5f}".format(acc))

    print('Test accuracy: ', round(session.run(accuracy, feed_dict={x: ts_features, y: ts_labels}), 3))
