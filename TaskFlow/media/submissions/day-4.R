data <- datasets::iris
data
hist(data$Sepal.Length,main="sepal length",xlab="count",ylab="size",col = rainbow(7),border = "black",angle = 45)


View(data)
barplot(data$Sepal.Length,data$Sepal.Width,data$Sepal.Length > 5 & data$Sepal.Width > 3,xlab='x-lable',ylab='y-lab',main="main")
a<-mean(data$Sepal.Length)
b<-mean(data$Sepal.Width)

m1<-c(a,b)
barplot(
  m1,
  xlab = "Sepal Length",
  ylab = "Sepal Width",
  main = "Average",
  names.arg = c("a", "b"),
  col = c("blue", "red"),  
  legend.text = c("aa", "bb"),  
  args.legend = list(x = "topright"))