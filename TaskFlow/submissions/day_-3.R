demo<-datasets::iris
demo

mean(demo$Sepal.Length)

median(demo$Sepal.Length)

a<-head(demo$Sepal.Length,3)
-table(a)

sort(-table(a))
names(sort(-table(a)))

names(sort(-table(a)))[1]
View(a)

table(a)

head(mutate(demo,Sepal.Length*2))

head(mutate(demo,Sepal.Length*2 , .after=Sepal.Width))
head(mutate(demo,SL.2=Sepal.Length*2 , .after=Sepal.Width))
