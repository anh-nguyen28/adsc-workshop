# STATS101 — Statistics and Machine Learning Foundations

## Mean, median and mode
The mean is the arithmetic average and is sensitive to outliers. The median is the middle value when sorted and is robust to outliers. The mode is the most frequent value. For skewed data the median usually describes the centre better.

## Variance and standard deviation
Variance is the average squared deviation from the mean. Standard deviation is its square root and is in the same units as the data, which makes it easier to interpret.

## Percentiles
The pth percentile is the value below which p percent of observations fall. The median is the 50th percentile. p95 and p99 are used to describe the tail of a distribution — the slow cases rather than the typical case.

## Normal distribution
The normal distribution is symmetric and defined by its mean and standard deviation. About 68 percent of values lie within one standard deviation of the mean, 95 percent within two and 99.7 percent within three.

## Correlation and causation
Correlation measures how two variables move together, between -1 and 1. Correlation does not imply causation: a confounding variable may drive both.

## Sampling
A sample is a subset of a population. A random sample gives every member an equal chance of selection. Biased sampling produces confident but wrong conclusions.

## Hypothesis testing
A null hypothesis states there is no effect. A p-value is the probability of observing data at least as extreme as yours if the null were true. A small p-value is evidence against the null, not proof of your hypothesis.

## Confidence intervals
A 95 percent confidence interval is a range that would contain the true parameter in 95 percent of repeated samples. Wider intervals mean more uncertainty.

## Supervised versus unsupervised learning
Supervised learning uses labelled examples to learn a mapping from inputs to outputs. Unsupervised learning finds structure in unlabelled data, such as clusters.

## Training, validation and test sets
The training set fits the model. The validation set tunes hyperparameters. The test set is touched once, at the end, to estimate real performance. Reusing the test set to make decisions quietly turns it into a validation set.

## Overfitting and underfitting
An overfitted model memorises training noise and generalises badly. An underfitted model is too simple to capture the pattern. The gap between training and validation error tells you which one you have.

## Bias-variance tradeoff
Bias is error from wrong assumptions; variance is error from sensitivity to the training sample. More complex models lower bias and raise variance.

## Cross-validation
K-fold cross-validation splits data into k parts, trains on k-1 and validates on the remaining one, rotating through all folds. It gives a more stable estimate than a single split.

## Gradient descent
Gradient descent iteratively moves parameters in the direction that most decreases the loss. The learning rate controls step size: too large and it diverges, too small and it crawls.

## Loss functions
Mean squared error is standard for regression. Cross-entropy is standard for classification. The loss is what the model optimises; it is not necessarily what you care about.

## Accuracy, precision and recall
Accuracy is the fraction of correct predictions and is misleading on imbalanced data. Precision is how many predicted positives were right. Recall is how many actual positives you found. F1 is their harmonic mean.

## Confusion matrix
A confusion matrix counts true positives, false positives, true negatives and false negatives. Almost every classification metric is a ratio of these four numbers.

## Regularisation
L1 regularisation drives weights to exactly zero and performs feature selection. L2 shrinks weights smoothly. Both penalise complexity to reduce overfitting.

## Feature scaling
Standardisation rescales features to zero mean and unit variance. Normalisation rescales to a fixed range. Distance-based and gradient-based methods need it; tree-based methods generally do not.
